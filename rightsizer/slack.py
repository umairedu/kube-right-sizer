import ssl

import certifi
from slack_sdk import WebClient


def send(token, channel, summary, html_report, patches, verify_ssl=True):
    # certifi, because some Python builds (python.org on macOS) ship without CA certs
    context = ssl.create_default_context(cafile=certifi.where())
    if not verify_ssl:
        # for networks that intercept TLS with their own CA
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    slack = WebClient(token=token, ssl=context)

    message = slack.chat_postMessage(channel=channel, text=summary)
    slack.files_upload_v2(
        channel=message["channel"],
        thread_ts=message["ts"],
        file_uploads=[
            {"filename": "resource-report.html", "content": html_report, "title": "Resource report"},
            {"filename": "recommendations.yaml", "content": patches, "title": "Patches"},
        ],
    )
