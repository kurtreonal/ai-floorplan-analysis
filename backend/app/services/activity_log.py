"""Administrative history without passwords, tokens, codes or private payloads."""
from app.models.account_security import AdminActivity


def record(db, actor, action, target_type, target_id, summary):
    db.add(AdminActivity(actor_id=actor.id, action=action, target_type=target_type,
        target_id=target_id, summary=summary[:500]))
