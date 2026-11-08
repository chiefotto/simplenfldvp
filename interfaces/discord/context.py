from services.context import RequestContext


def access_level_for(user, admin_role_id):
    if not admin_role_id:
        return "PUBLIC"
    role_ids = {str(role.id) for role in getattr(user, "roles", [])}
    if str(admin_role_id) in role_ids:
        return "ADMIN"
    return "PUBLIC"


def request_context(user, admin_role_id=None):
    return RequestContext(
        interface="discord",
        caller_id=str(user.id),
        access_level=access_level_for(user, admin_role_id),
    )
