import itertools
import re
from collections import namedtuple
from html import unescape

from auth import query
from integration import Integration

COURSE = query("piazza/course_id", staff=True)

SHORT_REGEX = r"@(?P<cid>[0-9]+)(_f(?P<fid>[0-9]+))?"
LONG_REGEX = r"https://piazza.com/class/{}\?cid=(?P<cid>[0-9]+)(_f(?P<fid>[0-9]+))?".format(COURSE)

Post = namedtuple("Post", ["subject", "content", "url", "full_cid"])


class PiazzaIntegration(Integration):
    def process(self):
        self.posts = {}
        for match in itertools.chain(
                re.finditer(SHORT_REGEX, self.message),
                re.finditer(LONG_REGEX, self.message),
        ):
            cid = int(match.group("cid"))
            fid_str = match.group("fid")
            full_cid = match.group("cid") + ("_f{}".format(fid_str) if fid_str else "")
            post = query("piazza/get_post", staff=True, cid=cid)
            subject = post["history"][0]["subject"]
            content = post["history"][0]["content"]

            if fid_str:
                fid = int(fid_str)  # 1 indexed
                curr_id = 0
                for child in post["children"]:
                    if child["type"] != "followup":
                        continue
                    curr_id += 1
                    if fid == curr_id:
                        break
                else:
                    return
                content = child["subject"]

            content = unescape(re.sub("<[^<]+?>", "", content))
            url = "https://piazza.com/class/{}?cid={}".format(COURSE, full_cid)

            self.posts[Post(subject, content, url, full_cid)] = None

    @property
    def text(self):
        out = self.message
        for post in self.posts:
            link = "<{}|@{}>".format(post.url, post.full_cid)
            out = out.replace("<{}>".format(post.url), link)
            out = re.sub(r"(?<!\|)(@{})".format(post.full_cid), link, out)
        return out

    @property
    def attachments(self):
        return [
            {
                "color": "#3575a8",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":piazza: *<{}|{}>* \n {}".format(
                                post.url, post.subject, post.content[:2500]
                            ),
                        },
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Open",
                            },
                            "value": "piazza_open_click",
                            "url": post.url,
                        },
                    },
                ]
            }
            for post in self.posts
        ]