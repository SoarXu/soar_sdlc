import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.ldap_sync import LdapSyncItem, LdapSyncRun
from app.models.user import User
from app.services.ldap_client import LdapConnectionError, LdapQueryError, ldap_client
from app.services.local_admin_service import ensure_local_admin_remains


class SyncItemError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def match_directory_user(db: Session, entry: dict) -> dict:
    result = dict(entry)
    external_id = normalize_external_id(entry.get("external_id"))
    result["external_id"] = external_id
    employee_no = _clean(entry.get("employee_no"))
    username = _clean(entry.get("username"))
    email = _clean(entry.get("email"))
    clauses = []
    if external_id:
        clauses.append(func.lower(User.ldap_external_id) == external_id)
    if employee_no:
        clauses.append(User.employee_no == employee_no)
    if username:
        clauses.append(func.lower(User.username) == username.casefold())
    if email:
        clauses.append(func.lower(User.email) == email.casefold())
    users = (
        db.query(User).filter(User.deleted == 0, or_(*clauses)).all()
        if clauses else []
    )

    external_matches = [
        user for user in users
        if external_id and normalize_external_id(user.ldap_external_id) == external_id
    ]
    if len(external_matches) > 1:
        return _matched_result(result, "conflict", None, "LDAP 唯一标识匹配到多个 SDLC 用户")
    if external_matches:
        user = external_matches[0]
        status = "linked" if entry.get("enabled", True) else "ad_disabled"
        return _matched_result(result, status, user, None)

    employee_matches = [user for user in users if employee_no and user.employee_no == employee_no]
    username_matches = [
        user for user in users
        if username and user.username and user.username.casefold() == username.casefold()
    ]
    email_matches = [
        user for user in users
        if email and user.email and user.email.casefold() == email.casefold()
    ]
    if len(employee_matches) > 1:
        match = _matched_result(result, "conflict", None, "工号匹配到多个 SDLC 用户")
    else:
        signal_users = {user.id: user for user in employee_matches + username_matches + email_matches}
        has_other_ldap_identity = any(
            normalize_external_id(user.ldap_external_id) not in {None, external_id}
            for user in signal_users.values()
        )
        if has_other_ldap_identity:
            match = _matched_result(result, "conflict", None, "匹配到的 SDLC 用户已绑定其他 AD 身份")
        elif len(signal_users) > 1:
            match = _matched_result(result, "conflict", None, "工号、账号或邮箱命中了不同用户")
        elif len(signal_users) == 1:
            match = _matched_result(result, "match_suggested", next(iter(signal_users.values())), None)
        else:
            match = _matched_result(result, "unlinked", None, None)
    if not entry.get("enabled", True):
        match["sync_status"] = "ad_disabled"
    return match


def sync_selected_users(db: Session, selections, initiated_by_user_id: int) -> dict:
    from app.services.ldap_config_service import _password, require_ready_config

    config = require_ready_config(db)
    password = _password(config)
    run = LdapSyncRun(
        initiated_by_user_id=initiated_by_user_id,
        status="running",
        total_count=len(selections),
    )
    db.add(run)
    db.flush()
    results = []
    counts = {"created": 0, "bound": 0, "updated": 0, "skipped": 0, "failed": 0}

    for selection in selections:
        external_id = normalize_external_id(selection.external_id)
        try:
            entry = ldap_client.search_user_by_external_id(config, password, external_id)
            if entry is None or normalize_external_id(entry.get("external_id")) != external_id:
                raise SyncItemError("DIRECTORY_USER_NOT_FOUND", "AD 域中未找到所选用户")
            entry = {**entry, "external_id": external_id}
            with db.begin_nested():
                outcome = _apply_decision(db, entry, selection.decision, selection.user_id)
                db.flush()
        except (LdapConnectionError, LdapQueryError) as error:
            outcome = _failure(external_id, "LDAP_QUERY_FAILED", str(error))
        except SyncItemError as error:
            outcome = _failure(external_id, error.code, error.message)
        except IntegrityError:
            outcome = _failure(external_id, "IDENTITY_CONFLICT", "LDAP 唯一标识、工号或账号已被其他用户使用")

        counts[outcome["status"]] += 1
        results.append(outcome)
        db.add(LdapSyncItem(
            run_id=run.id,
            external_id=external_id,
            decision=selection.decision,
            status=outcome["status"],
            user_id=outcome.get("user_id"),
            message=outcome.get("message"),
        ))

    run.created_count = counts["created"]
    run.bound_count = counts["bound"]
    run.updated_count = counts["updated"]
    run.skipped_count = counts["skipped"]
    run.failed_count = counts["failed"]
    run.status = "completed" if counts["failed"] == 0 else "partial_failed"
    run.completed_at = _now()
    db.commit()
    return {
        "run_id": run.id,
        "summary": {"total": len(selections), **counts},
        "items": results,
    }


def sync_bound_users(db: Session, initiated_by_user_id: int | None) -> dict:
    from app.services.ldap_config_service import _password, require_ready_config

    users = (
        db.query(User)
        .filter(
            User.deleted == 0,
            User.auth_source == "ldap",
            User.ldap_external_id.is_not(None),
        )
        .order_by(User.id.asc())
        .all()
    )
    run = LdapSyncRun(
        initiated_by_user_id=initiated_by_user_id,
        status="running",
        total_count=len(users),
    )
    db.add(run)
    db.flush()

    try:
        config = require_ready_config(db)
        password = _password(config)
    except HTTPException as error:
        message = _safe_config_error(error)
        results = [_failure(normalize_external_id(user.ldap_external_id), "LDAP_CONFIG_UNAVAILABLE", message) for user in users]
        for user, outcome in zip(users, results):
            _add_audit_item(db, run.id, user.ldap_external_id, "update", outcome, user.id)
        _finish_run(run, {"created": 0, "bound": 0, "updated": 0, "skipped": 0, "failed": len(users)}, "failed")
        db.commit()
        return _sync_response(run, results)

    results = []
    counts = {"created": 0, "bound": 0, "updated": 0, "skipped": 0, "failed": 0}
    for user in users:
        external_id = normalize_external_id(user.ldap_external_id)
        try:
            entry = ldap_client.search_user_by_external_id(config, password, external_id)
            if entry is None:
                with db.begin_nested():
                    locked_user = db.query(User).filter(User.id == user.id).with_for_update().one()
                    locked_user.is_active = False
                    locked_user.ldap_last_synced_at = _now()
                    outcome = _success(external_id, "updated", locked_user)
                    db.flush()
            elif normalize_external_id(entry.get("external_id")) != external_id:
                raise SyncItemError("DIRECTORY_USER_NOT_FOUND", "AD 域中未找到已绑定用户")
            else:
                entry = {**entry, "external_id": external_id}
                with db.begin_nested():
                    outcome = _apply_decision(db, entry, "update", None)
                    db.flush()
        except (LdapConnectionError, LdapQueryError) as error:
            outcome = _failure(external_id, "LDAP_QUERY_FAILED", str(error))
        except SyncItemError as error:
            outcome = _failure(external_id, error.code, error.message)
        except IntegrityError:
            outcome = _failure(external_id, "IDENTITY_CONFLICT", "LDAP 唯一标识、工号或账号已被其他用户使用")

        counts[outcome["status"]] += 1
        results.append(outcome)
        _add_audit_item(db, run.id, external_id, "update", outcome, outcome.get("user_id") or user.id)

    status_value = "completed" if counts["failed"] == 0 else "failed" if counts["failed"] == len(users) else "partial_failed"
    _finish_run(run, counts, status_value)
    db.commit()
    return _sync_response(run, results)


def list_sync_runs(db: Session, page: int, page_size: int) -> dict:
    query = db.query(LdapSyncRun)
    total = query.count()
    runs = query.order_by(LdapSyncRun.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    run_ids = [run.id for run in runs]
    failure_messages = {}
    if run_ids:
        first_failure_ids = (
            db.query(
                LdapSyncItem.run_id.label("run_id"),
                func.min(LdapSyncItem.id).label("item_id"),
            )
            .filter(LdapSyncItem.run_id.in_(run_ids), LdapSyncItem.status == "failed")
            .group_by(LdapSyncItem.run_id)
            .subquery()
        )
        failures = (
            db.query(LdapSyncItem.run_id, LdapSyncItem.message)
            .join(first_failure_ids, LdapSyncItem.id == first_failure_ids.c.item_id)
            .all()
        )
        for run_id, message in failures:
            failure_messages[run_id] = message
    items = []
    for run in runs:
        items.append({
            "id": run.id,
            "initiated_by_user_id": run.initiated_by_user_id,
            "status": run.status,
            "total_count": run.total_count,
            "created_count": run.created_count,
            "bound_count": run.bound_count,
            "updated_count": run.updated_count,
            "skipped_count": run.skipped_count,
            "failed_count": run.failed_count,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "error_summary": failure_messages.get(run.id),
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _add_audit_item(db, run_id, external_id, decision, outcome, user_id=None) -> None:
    db.add(LdapSyncItem(
        run_id=run_id,
        external_id=normalize_external_id(external_id) or "unknown",
        decision=decision,
        status=outcome["status"],
        user_id=user_id,
        message=outcome.get("message"),
    ))


def _finish_run(run, counts: dict, status_value: str) -> None:
    run.created_count = counts["created"]
    run.bound_count = counts["bound"]
    run.updated_count = counts["updated"]
    run.skipped_count = counts["skipped"]
    run.failed_count = counts["failed"]
    run.status = status_value
    run.completed_at = _now()


def _sync_response(run, results: list[dict]) -> dict:
    return {
        "run_id": run.id,
        "summary": {
            "total": run.total_count,
            "created": run.created_count,
            "bound": run.bound_count,
            "updated": run.updated_count,
            "skipped": run.skipped_count,
            "failed": run.failed_count,
        },
        "items": results,
    }


def _safe_config_error(error: HTTPException) -> str:
    if isinstance(error.detail, str) and error.detail in {
        "LDAP 集成尚未启用",
        "LDAP 配置尚未测试或测试后已发生变化",
        "LDAP 绑定密码无法解密，请检查 INTEGRATION_ENCRYPTION_KEY",
    }:
        return error.detail
    return "LDAP 配置不可用"


def _apply_decision(db: Session, entry: dict, decision: str, user_id: int | None) -> dict:
    match = match_directory_user(db, entry)
    external_id = entry["external_id"]
    matched = match.get("matched_user")
    if decision == "create":
        if not entry.get("enabled", True):
            raise SyncItemError("AD_USER_DISABLED", "AD 用户已禁用，不能创建")
        if match["sync_status"] != "unlinked":
            raise SyncItemError("IDENTITY_CONFLICT", "AD 用户已关联或存在待确认匹配")
        user = User(password_hash=get_password_hash(secrets.token_urlsafe(48)), deleted=0)
        db.add(user)
        _update_user(user, entry)
        db.flush()
        return _success(external_id, "created", user)
    if decision == "bind":
        if not entry.get("enabled", True):
            raise SyncItemError("AD_USER_DISABLED", "AD 用户已禁用，不能绑定")
        if match["sync_status"] != "match_suggested":
            code = "MATCH_CONFLICT" if match["sync_status"] == "conflict" else "BIND_NOT_SUGGESTED"
            raise SyncItemError(code, "只有唯一匹配建议的 AD 用户才能绑定")
        if not matched or matched["id"] != user_id:
            raise SyncItemError("BIND_TARGET_MISMATCH", "绑定目标与匹配建议不一致")
        user = (
            db.query(User)
            .filter(User.id == user_id, User.deleted == 0)
            .with_for_update()
            .first()
        )
        if user is None:
            raise SyncItemError("USER_NOT_FOUND", "待绑定的 SDLC 用户不存在")
        locked_external_id = normalize_external_id(user.ldap_external_id)
        if locked_external_id not in {None, external_id}:
            raise SyncItemError("MATCH_CONFLICT", "待绑定用户已绑定其他 AD 身份")
        try:
            ensure_local_admin_remains(db, user)
        except HTTPException as error:
            detail = error.detail if isinstance(error.detail, dict) else {}
            raise SyncItemError(
                detail.get("code", "LOCAL_ADMIN_REQUIRED"),
                detail.get("message", "系统必须保留至少一个启用的本地系统管理员"),
            ) from error
        _update_user(user, entry)
        return _success(external_id, "bound", user)
    if decision == "update":
        if not matched or match["sync_status"] not in {"linked", "ad_disabled"}:
            raise SyncItemError("NOT_LINKED", "AD 用户尚未绑定，不能更新")
        user = db.get(User, matched["id"])
        _update_user(user, entry)
        return _success(external_id, "updated", user)
    raise SyncItemError("INVALID_DECISION", "不支持的同步决策")


def _update_user(user: User, entry: dict) -> None:
    username = _clean(entry.get("username"))
    if not username:
        raise SyncItemError("MISSING_USERNAME", "LDAP 用户缺少登录账号属性")
    user.username = username
    user.employee_no = _clean(entry.get("employee_no"))
    user.full_name = _clean(entry.get("full_name")) or username
    user.email = _clean(entry.get("email"))
    user.mobile = _clean(entry.get("mobile"))
    user.department = _clean(entry.get("department"))
    user.auth_source = "ldap"
    user.ldap_external_id = entry["external_id"]
    user.ldap_dn = _clean(entry.get("dn"))
    user.ldap_last_synced_at = _now()
    user.is_active = bool(entry.get("enabled", True))
    user.must_change_password = False


def _matched_result(entry: dict, status: str, user: User | None, reason: str | None) -> dict:
    entry.update({
        "sync_status": status,
        "matched_user": _user_summary(user) if user else None,
        "conflict_reason": reason,
    })
    return entry


def _user_summary(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "employee_no": user.employee_no,
        "auth_source": user.auth_source,
    }


def _success(external_id: str, status: str, user: User) -> dict:
    db_id = user.id
    return {"external_id": external_id, "status": status, "user_id": db_id, "code": None, "message": None}


def _failure(external_id: str, code: str, message: str) -> dict:
    return {"external_id": external_id, "status": "failed", "user_id": None, "code": code, "message": message}


def _clean(value) -> str | None:
    normalized = str(value).strip() if value is not None else ""
    return normalized or None


def normalize_external_id(value) -> str | None:
    normalized = _clean(value)
    if normalized is None:
        return None
    try:
        return str(uuid.UUID(normalized))
    except ValueError:
        return normalized.casefold()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
