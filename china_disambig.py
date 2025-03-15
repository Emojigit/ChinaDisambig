#!/usr/bin/env python3

import re
from time import sleep
import requests

API_URL = "https://zh.wikipedia.org/w/api.php"

REDIRECT_REGEX = re.compile(
    r"^#([Rr][Ee][Dd][Ii][Rr][Ee][Cc][Tt]|重定向) *\[\[(.*?)\]\] *(\n|$)")
REDIRECT_FORMAT = r"#REDIRECT [[{target}]]"

DISAMBIG_REGEX = re.compile(
    r"{{(([Tt]([Ee][Mm][Pp][Ll][Aa][Tt][Ee])?|模板):)?(消歧[義义]|分歧義|[Dd]ab|分歧页?|[Dd]isamb(ig(uous)?|uation page)?|[Aa]imai)\|?.*?}}",
    flags=0
)

HANT_TITLE_FORMAT = r"{year}年中國"
HANS_TITLE_FORMAT = r"{year}年中国"

PRE_HANDOVER_FORMAT = r"""按[[de facto|實際上]]的[[海峽兩岸關係|兩岸政治情況]]，'''{year}年中國'''的重大事件分述於以下條目：

* {year}年中華人民共和國，即[[{year}年中國大陸]]，{year}年中華人民共和國（不含台港澳）的重大事件；
* {year}年中華民國，即[[{year}年臺灣]]，{year}年臺灣的重大事件。

== 參見 ==

* [[{year}年香港]]，{year}年英屬香港的重大事件。
* [[{year}年澳門]]，{year}年葡屬澳門的重大事件。

{{{{disambig|Cat=兩岸分治後各年中國消歧義}}}}"""

POST_HK_HANDOVER_FORMAT = r"""按[[de facto|實際上]]的[[海峽兩岸關係|兩岸政治情況]]，'''{year}年中國'''的重大事件分述於以下條目：

* {year}年中華人民共和國，按地區分爲——
** [[{year}年中國大陸]]，{year}年中華人民共和國（不含台港澳）的重大事件；
** [[{year}年香港]]，{year}年香港特別行政區的重大事件；
* {year}年中華民國，即[[{year}年臺灣]]，{year}年臺灣的重大事件。

== 參見 ==
* [[{year}年澳門]]，{year}年葡屬澳門的重大事件。

{{{{disambig|Cat=兩岸分治後各年中國消歧義}}}}"""

POST_ALL_HANDOVER_FORMAT = r"""按[[de facto|實際上]]的[[海峽兩岸關係|兩岸政治情況]]，'''{year}年中國'''的重大事件分述於以下條目：

* {year}年中華人民共和國，按地區分爲——
** [[{year}年中國大陸]]，{year}年中華人民共和國（不含港澳兩個特別行政區及從未實際管轄的臺灣地區）的重大事件；
** [[{year}年香港]]，{year}年香港特別行政區的重大事件；
** [[{year}年澳門]]，{year}年澳門特別行政區的重大事件；
* {year}年中華民國，即[[{year}年臺灣]]，{year}年臺灣的重大事件。

{{{{disambig|Cat=兩岸分治後各年中國消歧義}}}}"""

# Don't have to worry about 1997 and 1999 cuz already created


def get_template(year: int) -> str:
    if year < 1997:
        return PRE_HANDOVER_FORMAT
    if year < 1999:
        return POST_HK_HANDOVER_FORMAT
    return POST_ALL_HANDOVER_FORMAT


def check_page_name(year: int, S: requests.Session) -> list[str]:
    HANT_TITLE = HANT_TITLE_FORMAT.format(year=year)
    HANS_TITLE = HANS_TITLE_FORMAT.format(year=year)

    API_PARAMS = {
        "action": "query",
        "prop": "revisions",
        "titles": HANT_TITLE + "|" + HANS_TITLE,
        "rvprop": "content",
        "rvslots": "main",
        "formatversion": "2",
        "format": "json"
    }

    R = S.get(url=API_URL, params=API_PARAMS)
    DATA = R.json()

    PAGES = DATA["query"]["pages"]
    page_titles = []

    for page in PAGES:
        if "missing" in page:
            print("Page " + page["title"] + " missing.")
            continue
        content = page["revisions"][0]["slots"]["main"]["content"]
        print("Page " + page["title"] + " has content: " + content)

        if DISAMBIG_REGEX.search(content):
            print("Disambiguation found in " + page["title"] + "\n")
            return []
        page_titles.append(page["title"])
    return page_titles


def edit_page(title: str, content: str, summary: str, S: requests.Session):
    TOKEN_PARAMS = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    R = S.get(url=API_URL, params=TOKEN_PARAMS)
    DATA = R.json()
    CSRF_TOKEN = DATA['query']['tokens']['csrftoken']

    API_PARAMS = {
        "action": "edit",
        "title": title,
        "token": CSRF_TOKEN,
        "format": "json",
        "text": content,
        "summary": summary + " // github.com/Emojigit/ChinaDisambig",
        "notminor": True,
        "bot": True,
    }

    S.post(url=API_URL, data=API_PARAMS)


def do_edit_queue(pending_edits: tuple[tuple[str, str, str]], S: requests.Session) -> bool:
    """Allow user to review edits before proceeding

    Parameters
    ----------
    pending_edits : tuple[tuple[str, str, str]]
        Title, content, summary.
    """

    while True:
        print(str(len(pending_edits)) + " edit to be done:")

        for i, (title, content, summary) in enumerate(pending_edits):
            print(str(i) + ": " + title + " (" + summary + ")")

        print(
            "Enter the edit ID to view its content, \"K\" to skip all, or empty to proceed.")
        user_input = input("> ").lower()

        if user_input == "k":
            return False
        if user_input == "":
            for i, (title, content, summary) in enumerate(pending_edits):
                print("Doing edit #" + str(i))
                edit_page(title, content, summary, S)
            return True

        try:
            view_id = int(user_input)

            print("\nContent of edit #" + user_input + ":\n")
            print(pending_edits[view_id][1])
            print("\n")
        except ValueError:
            print("Invalid input.")


def work_on_page(year: int, S: requests.Session):
    print("Working on year " + str(year))

    page_names = check_page_name(year, S)
    if len(page_names) == 0:
        sleep(3)  # Let's sleep a while
        return

    edit_queue = []
    for i, title in enumerate(page_names):
        if i == 0:
            edit_queue.append((
                title, get_template(year).format(year=year),
                "半自動建立[[Category:兩岸分治後各年中國消歧義|]]（主頁面）：見[[User:1F616EMO/中國消歧義]]。"
            ))
        else:
            edit_queue.append((
                title, REDIRECT_FORMAT.format(target=page_names[0]),
                "半自動建立[[Category:兩岸分治後各年中國消歧義|]]（繁簡重定向）：見[[User:1F616EMO/中國消歧義]]。"
            ))

    if do_edit_queue(edit_queue, S):
        print("Succeed\n")
    else:
        print("Skipped\n")


if __name__ == "__main__":
    S = requests.Session()

    LOGIN_TOKEN_PARAMS = {
        "action": "query",
        "meta": "tokens",
        "type": "login",
        "format": "json",
    }

    R = S.get(url=API_URL, params=LOGIN_TOKEN_PARAMS)
    DATA = R.json()
    LOGIN_TOKEN = DATA['query']['tokens']['logintoken']

    LOGIN_PARAMS = {
        'action': "login",
        'lgname': input("Username: "),
        'lgpassword': input("Botpassword: "),
        'lgtoken': LOGIN_TOKEN,
        'format': "json"
    }

    LOWER_BOUND = int(input("Lower bound (year): "))
    UPPER_BOUND = int(input("Upper bound (year): "))
    assert LOWER_BOUND < UPPER_BOUND

    R = S.post(url=API_URL, data=LOGIN_PARAMS)
    DATA = R.json()
    assert DATA['login']['result'] == 'Success'

    print("\n")

    for year in range(LOWER_BOUND, UPPER_BOUND + 1):
        work_on_page(year, S)
