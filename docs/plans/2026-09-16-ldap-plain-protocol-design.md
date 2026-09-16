# LDAP 明文协议选项设计

## 背景

当前 LDAP 集成只支持 `LDAP + StartTLS` 和 `LDAPS`。测试环境的后端容器无法完成 StartTLS 证书校验，因此需要在保留现有安全协议语义的前提下，增加一个显式的明文 LDAP 选项用于目标环境。

## 决策

新增协议值 `plain`，形成三个明确选项：

- `plain`：LDAP（不加密），默认端口 389，TCP 建连后直接执行 Simple Bind。
- `ldap`：LDAP + StartTLS，默认端口 389，保持现有证书校验和连接顺序。
- `ldaps`：LDAPS，默认端口 636，保持现有证书校验和自动绑定行为。

不复用或重定义现有 `ldap` 值，避免历史配置在升级后静默降级为明文。`plain` 长度为 5，现有 `VARCHAR(8)` 字段可以容纳，因此不需要数据库迁移。

## 后端行为

配置写入模型允许 `plain`、`ldap` 和 `ldaps`。目录查询连接与 LDAP 用户登录连接遵循同一协议分支：

- `plain`：`use_ssl=False`、`auto_bind=False`，依次调用 `open()` 和 `bind()`，不创建 TLS 上下文，不调用 `start_tls()`。
- `ldap`：继续创建要求证书校验的 TLS 上下文，依次调用 `open()`、`start_tls()` 和 `bind()`。
- `ldaps`：继续创建要求证书校验的 TLS 上下文，通过 SSL 建连并自动绑定。

明文模式的网络失败和绑定失败继续映射到现有稳定错误，不新增错误契约。

## 前端行为

协议分段控件按顺序显示：`LDAP（不加密）`、`LDAP + StartTLS`、`LDAPS`。选择前两项时，如果当前端口为 636，则自动切换为 389；选择 LDAPS 时，如果当前端口为 389，则自动切换为 636。默认配置仍为 LDAPS 636。

协议变化继续作为连接身份变化处理，要求重新填写绑定密码并重新测试后才能启用。

## 测试

- 配置 API 接受并回读 `plain`。
- LDAP 目录客户端在 `plain` 模式下只执行 `open()`、`bind()`，绝不执行 `start_tls()`。
- LDAP 用户认证在 `plain` 模式下只执行 `open()`、`bind()`。
- 原有 StartTLS 和 LDAPS 测试继续通过。
- 前端源码测试确认三个协议选项和端口切换规则。

## 安全边界

`plain` 会通过未加密连接传输 LDAP Simple Bind 凭据，只能在业务方明确选择且目标 AD 策略允许时使用。系统不会自动把 StartTLS 配置降级为明文，也不会在 TLS 失败后自动回退到 `plain`。
