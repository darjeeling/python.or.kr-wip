import httpx
from django.conf import settings
from .models import GitHubSponsor


def sync_github_sponsors(org_name: str):
    """
    GitHub 스폰서 정보를 동기화하는 함수

    Args:
        org_name (str): GitHub 조직 이름 (예: pythonkr)
    """
    if not org_name:
        return

    # GitHub GraphQL API 엔드포인트
    url = "https://api.github.com/graphql"

    # GraphQL 쿼리
    query = """
    query($org: String!) {
      organization(login: $org) {
        sponsorshipsAsMaintainer(first: 100) {
          nodes {
            sponsorEntity {
              ... on User {
                login
                name
                avatarUrl
              }
            }
            tier {
              name
              monthlyPriceInDollars
            }
            isActive
          }
        }
      }
    }
    """

    # GitHub API 호출
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }

    variables = {"org": org_name}

    try:
        response = httpx.post(
            url, json={"query": query, "variables": variables}, headers=headers
        )
        if response.status_code == 200:
            data = response.json()
            sponsorships = (
                data.get("data", {})
                .get("organization", {})
                .get("sponsorshipsAsMaintainer", {})
                .get("nodes", [])
            )

            # 기존 스폰서 비활성화
            GitHubSponsor.objects.filter(is_active=True).update(is_active=False)

            # 새로운 스폰서 정보 저장
            for sponsorship in sponsorships:
                sponsor = sponsorship.get("sponsorEntity", {})
                tier = sponsorship.get("tier", {})

                GitHubSponsor.objects.update_or_create(
                    login=sponsor.get("login"),
                    defaults={
                        "name": sponsor.get("name"),
                        "avatar_url": sponsor.get("avatarUrl"),
                        "tier_name": tier.get("name"),
                        "monthly_amount": tier.get("monthlyPriceInDollars"),
                        "is_active": sponsorship.get("isActive", True),
                    },
                )

            return True

    except Exception as e:
        print(f"GitHub 스폰서 동기화 중 오류 발생: {str(e)}")
        return False
