from __future__ import annotations

from datetime import datetime, timezone

from avenor.db import init_db, session_scope
from avenor.models import Commit, Contributor, Issue, PullRequest
from avenor.services.metrics import (
    get_activity_series,
    get_commit_domain_breakdown,
    get_new_contributors_series,
    get_top_contributors,
)
from avenor.services.repositories import add_repository


def test_metrics_aggregate_repository_activity() -> None:
    init_db()
    with session_scope() as session:
        repository = add_repository(session, "https://github.com/chaoss/augur")
        session.add(
            Issue(
                repository_id=repository.id,
                external_id="i1",
                number=1,
                title="Issue",
                state="open",
                created_at=datetime(2024, 1, 4, tzinfo=timezone.utc),
            )
        )
        session.add(
            PullRequest(
                repository_id=repository.id,
                external_id="p1",
                number=2,
                title="PR",
                state="open",
                created_at=datetime(2024, 1, 7, tzinfo=timezone.utc),
            )
        )
        session.add(
            Commit(
                repository_id=repository.id,
                sha="abc",
                message="commit",
                author_name="Dev",
                author_email="dev@example.com",
                authored_at=datetime(2024, 1, 9, tzinfo=timezone.utc),
            )
        )
        session.add(
            Contributor(
                repository_id=repository.id,
                source="git",
                display_name="Dev",
                email="dev@example.com",
                first_seen_at=datetime(2024, 1, 9, tzinfo=timezone.utc),
                contributions_count=3,
            )
        )
        session.add(
            Contributor(
                repository_id=repository.id,
                source="github",
                login="octo",
                display_name="Octo",
                first_seen_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
                contributions_count=5,
            )
        )

        activity = get_activity_series(session, repository.id)
        top = get_top_contributors(session, repository.id)
        new_contributors = get_new_contributors_series(session, repository.id)
        domains = get_commit_domain_breakdown(session, repository.id)

    assert activity["issues"][0]["value"] == 1
    assert activity["pull_requests"][0]["value"] == 1
    assert activity["commits"][0]["value"] == 1
    assert top[0]["value"] == 5
    assert len(new_contributors) == 2
    assert domains[0]["label"] == "example.com"
