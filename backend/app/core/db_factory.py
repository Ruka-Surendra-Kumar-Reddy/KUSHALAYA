from sqlalchemy import create_engine


class DatabaseFactory:

    @staticmethod
    def create_engine(database_url: str):

        if database_url.startswith("sqlite"):
            return create_engine(
                database_url,
                connect_args={
                    "check_same_thread": False
                }
            )

        return create_engine(
            database_url,
            pool_pre_ping=True
        )