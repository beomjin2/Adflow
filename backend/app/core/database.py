from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_missing_columns():
    """모델에 새로 생긴 컬럼을 기존 테이블에 붙인다.

    create_all()은 없는 '테이블'만 만들고 없는 '컬럼'은 만들지 않는다. 운영 DB는
    이미 있는 테이블이라, 캐릭터 시트 칸을 늘려도 그대로 두면 no such column으로 죽는다.
    Alembic을 들이기엔 스키마가 작아서 여기서 ALTER TABLE만 돌린다 — 컬럼을 더하기만
    하고 지우거나 바꾸지 않으므로, 예전 코드로 되돌려도 DB는 그대로 동작한다.
    """
    import json

    from sqlalchemy import JSON, inspect, text

    def blank_for(column):
        """새 컬럼에 채울 초기값. ADD COLUMN은 기존 행을 NULL로 두는데, 응답 스키마의
        list[str]·dict는 None을 받지 않아 그대로 두면 GET이 500으로 죽는다.

        모델에 적어둔 default를 그대로 쓴다. default가 없으면 None을 돌려주고
        호출부가 UPDATE를 건너뛴다 — 무엇으로 채울지 여기서 지어내지 않는다.
        """
        default = column.default
        if default is None:
            return None
        if default.is_callable:
            # SQLAlchemy가 default=list를 ctx 인자를 받는 래퍼로 감싸 둔다.
            # 인자 없이 부르면 TypeError가 난다 — 실행 컨텍스트가 없으니 None을 넘긴다.
            value = default.arg(None)
        elif default.is_scalar:
            value = default.arg
        else:
            return None
        if value is None:
            return None
        return json.dumps(value) if isinstance(column.type, JSON) else value

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all이 방금 통째로 만들었다
            have = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in have:
                    continue
                ddl = column.type.compile(engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl}'))
                blank = blank_for(column)
                if blank is not None:
                    conn.execute(
                        text(f'UPDATE "{table.name}" SET "{column.name}" = :blank'),
                        {"blank": blank},
                    )


def init_db():
    from app import models  # noqa: F401  ensures models are registered before create_all
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
