from Database import Platform, SyncSessionLocal



def get_platform_credentials_sync(api_name: str) -> Platform:
    with SyncSessionLocal() as session:
        platform = session.query(Platform).filter_by(api_name=api_name).first()
        if not platform:
            return None
        return platform