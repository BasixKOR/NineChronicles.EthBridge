import argparse
import optparse
import time
import datetime
import sys
from typing import Any, Awaitable, Callable, Optional
import asyncio

import code

import slack_sdk

from models import SlackMessage, UnwrappingFailureEvent, WrappingEvent, UnwrappingEvent, WrappingFailureEvent, RefundEvent, Address, TxId
from ncscan import get_transaction
from parser import parse_slack_response


parser = argparse.ArgumentParser()
parser.add_argument("TOKEN")
parser.add_argument("CHANNEL_NAME")
parser.add_argument("-i", "--interactive", action="store_true")
args = parser.parse_args()

TOKEN = args.TOKEN
CHANNEL_NAME = args.CHANNEL_NAME
INTERACTIVE = args.interactive


client = slack_sdk.web.WebClient(TOKEN)
bot_id = client.users_profile_get().get("profile")["bot_id"]


def get_channel_id_from_channel_name(name: str) -> str:
    for channel in client.conversations_list()["channels"]:
        if channel["name"] == name:
            return channel["id"]

    raise KeyError(name)


channel_id = get_channel_id_from_channel_name(CHANNEL_NAME)
events = []

OLDEST = "1630854000.0"
LATEST = str(
    (
        datetime.datetime.fromtimestamp(time.time()) - datetime.timedelta(hours=2)
    ).timestamp()
)

cursor = None
while True:
    response = client.conversations_history(
        channel=channel_id, cursor=cursor, oldest=OLDEST, latest=LATEST
    )

    messages = response["messages"]

    events += list(filter(lambda x: x is not None, map(parse_slack_response, messages)))
    if response["response_metadata"] is None:
        break

    cursor = response["response_metadata"]["next_cursor"]


Handler = Callable[[Any], Awaitable[None]]
handlers = dict[type, list[Handler]]()


def handle(_type: type) -> Callable[[Handler], None]:
    def decorator(f: Handler) -> None:
        if _type not in handlers:
            handlers[_type] = list()

        handlers[_type].append(f)

    return decorator


total_fee = 0.0


@handle(WrappingEvent)
async def count_total_fee(e: WrappingEvent):
    global total_fee

    total_fee += e.fee

failure_events = list[SlackMessage]()

@handle(WrappingFailureEvent)
async def collect_wrapping_failure_event(e: WrappingFailureEvent):
    failure_events.append(e)


refund_events = list[RefundEvent]()

@handle(RefundEvent)
async def collect_refund_event(e: RefundEvent):
    refund_events.append(e)


# [request_txid, response_txid, recipient, type, amount]
gone_txs = list[tuple[TxId, TxId, Address, str, float]]()


@handle(UnwrappingEvent)
async def validate_unwrapping_event(e: UnwrappingEvent):
    txid = e.response_txid
    tx = await get_transaction(txid)
    if tx is None:
        gone_txs.append((e.request_txid, txid, e.recipient, "unwrapping", e.amount))
        try:
            messages: list[dict] = client.conversations_replies(channel=channel_id, ts=e.ts).get(
                "messages"
            )
            if any(filter(lambda x: isinstance(x, dict) and "bot_id" in x and x["bot_id"] == bot_id, messages)):
                return

            client.chat_postMessage(
                channel=channel_id,
                text="@dogeon this transaction seems gone.",
                thread_ts=e.ts,
                as_user=True,
                link_names=True,
            )
        except Exception as exc:
            print("Exception", exc)
            pass


@handle(WrappingEvent)
async def validate_wrapping_event(e: WrappingEvent):
    if e.refund_txid is None:
        return

    txid = e.refund_txid
    tx = await get_transaction(txid)
    if tx is None and e.refund_amount:
        gone_txs.append((e.request_txid, txid, e.sender, "refund", e.refund_amount))
        try:
            messages: list[dict] = client.conversations_replies(channel=channel_id, ts=e.ts).get(
                "messages"
            )
            if any(filter(lambda x: isinstance(x, dict) and "bot_id" in x and x["bot_id"] == bot_id, messages)):
                return

            client.chat_postMessage(
                channel=channel_id,
                text="@dogeon this transaction seems gone.",
                thread_ts=e.ts,
                as_user=True,
            )

        except Exception as exc:
            print("Exception", exc)
            pass

@handle(RefundEvent)
async def validate_refund_event(e: RefundEvent):
    txid = e.refund_txid

    tx = await get_transaction(txid)
    if tx is None:
        gone_txs.append((e.request_txid, txid, e.address, "refund", e.refund_amount))
        try:
            messages: list[dict] = client.conversations_replies(channel=channel_id, ts=e.ts).get(
                "messages"
            )
            if any(filter(lambda x: isinstance(x, dict) and "bot_id" in x and x["bot_id"] == bot_id, messages)):
                return

            client.chat_postMessage(
                channel=channel_id,
                text="@dogeon this transaction seems gone.",
                thread_ts=e.ts,
                as_user=True,
                link_names=True,
            )

        except Exception as exc:
            print("Exception", exc)
            pass

for event in events:
    t = type(event)

    if t in handlers:
        for handler in handlers[t]:
            asyncio.run(handler(event))

print("Earned", total_fee, "NCG")
print(*gone_txs, sep="\n")

print(failure_events)

if INTERACTIVE:
    code.interact(local=locals())
