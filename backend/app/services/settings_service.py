"""Database-backed application configuration (password policy etc.)."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.setting import AppSetting
from app.utils.crypto import PasswordPolicy, policy_from_dict, policy_to_dict

KEY_PASSWORD_POLICY = "password_policy"


class SettingsService:
    """Read/write persisted application settings.

    For MVP only the credential-generation password policy is stored here;
    this keeps the policy configurable at runtime without redeploys.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_password_policy(self) -> PasswordPolicy:
        row = self._db.get(AppSetting, KEY_PASSWORD_POLICY)
        if row is None:
            return PasswordPolicy()
        try:
            return policy_from_dict(json.loads(row.value_json))
        except (ValueError, TypeError, KeyError):
            return PasswordPolicy()

    def set_password_policy(self, policy: PasswordPolicy) -> PasswordPolicy:
        policy.validate()
        row = self._db.get(AppSetting, KEY_PASSWORD_POLICY)
        if row is None:
            row = AppSetting(
                key=KEY_PASSWORD_POLICY,
                value_json=json.dumps(policy_to_dict(policy)),
            )
            self._db.add(row)
        else:
            row.value_json = json.dumps(policy_to_dict(policy))
        self._db.commit()
        return policy