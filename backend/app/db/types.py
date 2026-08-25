from sqlalchemy import BigInteger
from sqlalchemy.dialects.mysql import BIGINT as MySQLBigInteger


UnsignedBigInteger = BigInteger().with_variant(MySQLBigInteger(unsigned=True), "mysql")
