from tiles_ai.contracts import PermissionDecision, PermissionTier, evaluate


def test_non_side_effect_always_executes():
    for tier in PermissionTier:
        assert evaluate(tier, is_side_effect=False) is PermissionDecision.EXECUTE


def test_read_only_rejects_side_effects():
    assert (
        evaluate(PermissionTier.READ_ONLY, is_side_effect=True)
        is PermissionDecision.REJECT
    )


def test_draft_queues_side_effects():
    assert (
        evaluate(PermissionTier.DRAFT, is_side_effect=True)
        is PermissionDecision.QUEUE
    )
    # Approval is irrelevant for draft — it always queues.
    assert (
        evaluate(PermissionTier.DRAFT, is_side_effect=True, approved=True)
        is PermissionDecision.QUEUE
    )


def test_autonomous_requires_approval_to_execute():
    assert (
        evaluate(PermissionTier.AUTONOMOUS, is_side_effect=True, approved=False)
        is PermissionDecision.QUEUE
    )
    assert (
        evaluate(PermissionTier.AUTONOMOUS, is_side_effect=True, approved=True)
        is PermissionDecision.EXECUTE
    )
