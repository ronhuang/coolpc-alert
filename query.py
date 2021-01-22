from bs4 import BeautifulSoup
from bs4.element import Tag
from github import Github
from github.Issue import Issue
import os
import re
import requests
import sys
from typing import List, NamedTuple, Union


name_price_re = re.compile(r"(.*), \$(\d+) .*$")
criteria_re = re.compile(r"(.*)~~~(.*)$")
item_re = re.compile(r"^\| (.+) \| (.+) \|$")


class Item(NamedTuple):
    name: str
    price: str


class Criteria(NamedTuple):
    category: str
    subcategory: str

    @classmethod
    def from_issue(cls, issue: Issue):
        m = criteria_re.match(issue.title)
        if m:
            criteria = Criteria(m.group(1), m.group(2))
            return criteria
        else:
            return None


def query(
    criteria: Union[Criteria, None], local_path: Union[str, None] = None
) -> List[Item]:
    if criteria is None:
        return list()

    content = None
    if local_path:
        with open(local_path, encoding="utf-8") as f:
            content = f.read()
    else:
        url = "http://www.coolpc.com.tw/evaluate.php"
        resp = requests.get(url)
        content = resp.text

    soup = BeautifulSoup(content, features="html.parser")

    column: Tag = soup.find(text=criteria.category)
    row: Tag = column.parent

    items: List[Item] = list()
    extras: List[Item] = list()
    capture_extras = False
    for group in row.find_all("optgroup"):
        if criteria.subcategory == group["label"]:
            for option in group.find_all("option"):
                if option.has_attr("disabled"):
                    continue
                m = name_price_re.match(option.text)
                if m:
                    item = Item(m.group(1), m.group(2))
                    items.append(item)
            capture_extras = True
        elif capture_extras:
            for option in group.find_all("option"):
                if option.has_attr("disabled"):
                    continue
                m = name_price_re.match(option.text)
                if m:
                    item = Item(m.group(1), m.group(2))
                    extras.append(item)
            break

    return [item for item in items if item not in extras]


def get_existing_from_issue(issue: Issue) -> List[Item]:
    items: List[Item] = list()

    lines = issue.body.splitlines()
    if len(lines) <= 2:
        # first two lines do not contain items
        return items

    for line in lines[2:]:
        m = item_re.match(line)
        if m:
            item = Item(m.group(1), m.group(2))
            items.append(item)

    return items


def update_issues(access_token: str, local_path: Union[str, None] = None):
    g = Github(access_token)
    full_name = os.getenv("GITHUB_REPOSITORY", "ronhuang/coolpc-alert")
    repo = g.get_repo(full_name)
    for issue in repo.get_issues(state="open"):
        criteria = Criteria.from_issue(issue)

        current_items = query(criteria, local_path)
        previous_items = get_existing_from_issue(issue)
        new_items = [item for item in current_items if item not in previous_items]
        missing_items = [item for item in previous_items if item not in current_items]

        if (len(new_items) + len(missing_items)) > 0:
            comment: List[str] = list()
            if len(new_items) > 0:
                comment.append("**New items**:")
                comment.append(to_markdown(new_items))
                comment.append("")
            if len(missing_items) > 0:
                comment.append("**Missing items**:")
                comment.append(to_markdown(missing_items))
                comment.append("")

            issue.edit(body=to_markdown(current_items))
            issue.create_comment("\n".join(comment))

            print(f"Updated issue #{issue.number} {issue.title}")
        else:
            print(f"No update for issue #{issue.number} {issue.title}")


def to_markdown(items: List[Item]):
    content: List[str] = list()

    content.append("| Name | Price |")
    content.append("| ---- | ----- |")
    for item in items:
        content.append(f"| {item.name} | {item.price} |")

    return "\n".join(content)


if __name__ == "__main__":
    access_token = sys.argv[1] if len(sys.argv) > 1 else os.getenv("GITHUB_TOKEN")
    local_path = sys.argv[2] if len(sys.argv) > 2 else None
    update_issues(access_token, local_path)
    sys.exit(0)
