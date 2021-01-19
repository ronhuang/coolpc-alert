from bs4 import BeautifulSoup
from bs4.element import Tag
from github import Github
import re
import requests
import sys
from typing import List, NamedTuple, Union


name_price_re = re.compile(r"(.*), \$(\d+) .*$")
criteria_re = re.compile(r"(.*)~~~(.*)$")


class Item(NamedTuple):
    name: str
    price: str


class Criteria(NamedTuple):
    category: str
    subcategory: str


def query(criteria: Criteria, local_path: Union[str, None] = None):
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


def update_issues(access_token: str, local_path: Union[str, None] = None):
    g = Github(access_token)
    repo = g.get_user().get_repo("coolpc-alert")
    for issue in repo.get_issues():
        m = criteria_re.match(issue.title)
        if m:
            criteria = Criteria(m.group(1), m.group(2))
            results = query(criteria, local_path)
            issue.edit(body=to_markdown(results))


def to_markdown(items: List[Item]):
    content: List[str] = list()

    content.append("| Name | Price |")
    content.append("| ---- | ----- |")
    for item in items:
        content.append(f"| {item.name} | {item.price} |")

    return "\n".join(content)


if __name__ == "__main__":
    # res = query("固態硬碟 M.2｜SSD", "M.2 (PCIe) SSD固態硬碟", local_path)
    update_issues(sys.argv[1])
    sys.exit(0)
