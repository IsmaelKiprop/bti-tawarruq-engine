"""Who may invite whom — no database. HTTP coverage lives in test_ops_login.py."""

from tawarruq.enums import ApiKeyRole
from tawarruq.services.rbac import INVITE_TARGETS_BY_CREATOR, may_invite


def test_super_admin_invite_targets():
    actor = ApiKeyRole.PLATFORM_ADMIN
    allowed = {
        ApiKeyRole.PLATFORM_ADMIN,
        ApiKeyRole.BTI_OPS,
        ApiKeyRole.BTI_FINANCE,
        ApiKeyRole.INSTITUTION_ADMIN,
        ApiKeyRole.SHARIAH_OFFICER,
        ApiKeyRole.RECONCILER,
    }
    blocked = {
        ApiKeyRole.INSTITUTION_OPS,
        ApiKeyRole.FI_APPROVER,
        ApiKeyRole.API_CLIENT,
        ApiKeyRole.READ_ONLY,
        ApiKeyRole.AGENT_DEALER,
    }
    assert INVITE_TARGETS_BY_CREATOR[actor] == allowed
    for role in allowed:
        assert may_invite(actor, role)
    for role in blocked:
        assert not may_invite(actor, role)


def test_fi_admin_invite_targets():
    actor = ApiKeyRole.INSTITUTION_ADMIN
    allowed = {
        ApiKeyRole.INSTITUTION_ADMIN,
        ApiKeyRole.INSTITUTION_OPS,
        ApiKeyRole.FI_APPROVER,
        ApiKeyRole.SHARIAH_OFFICER,
        ApiKeyRole.RECONCILER,
    }
    blocked = {ApiKeyRole.PLATFORM_ADMIN, ApiKeyRole.BTI_OPS, ApiKeyRole.BTI_FINANCE}
    assert INVITE_TARGETS_BY_CREATOR[actor] == allowed
    for role in allowed:
        assert may_invite(actor, role)
    for role in blocked:
        assert not may_invite(actor, role)


def test_bti_ops_invite_targets():
    actor = ApiKeyRole.BTI_OPS
    assert INVITE_TARGETS_BY_CREATOR[actor] == {ApiKeyRole.INSTITUTION_ADMIN}
    assert may_invite(actor, ApiKeyRole.INSTITUTION_ADMIN)
    for role in (
        ApiKeyRole.PLATFORM_ADMIN,
        ApiKeyRole.BTI_OPS,
        ApiKeyRole.BTI_FINANCE,
        ApiKeyRole.INSTITUTION_OPS,
        ApiKeyRole.FI_APPROVER,
    ):
        assert not may_invite(actor, role)


def test_non_creators_cannot_invite():
    for actor in (
        ApiKeyRole.INSTITUTION_OPS,
        ApiKeyRole.FI_APPROVER,
        ApiKeyRole.BTI_FINANCE,
        ApiKeyRole.SHARIAH_OFFICER,
        ApiKeyRole.RECONCILER,
        None,
    ):
        assert not may_invite(actor, ApiKeyRole.INSTITUTION_OPS)
        assert not may_invite(actor, ApiKeyRole.INSTITUTION_ADMIN)
