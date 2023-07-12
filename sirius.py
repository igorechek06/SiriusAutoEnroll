import asyncio
import json
from base64 import b64encode
from datetime import datetime, timedelta
from os import get_terminal_size
from os.path import exists

import aiohttp
from rich import print


def create_user_session(login: str, password: str) -> aiohttp.ClientSession:
    token = b64encode(f"{login}:{password}".encode("UTF-8")).decode("UTF-8")
    return aiohttp.ClientSession(headers={"authorization": f"Basic {token}"})


async def get_user_and_events(
    session: aiohttp.ClientSession,
) -> tuple[dict, list[dict]]:
    async with session.get(
        "https://online.sochisirius.ru/schedule?task=getTimeline&mobile=1&onRec=1&app=100220230510118067"
    ) as response:
        data = await response.json()
        user = data["user"]
        events = [event for events in data["events"].values() for event in events]
        return (user, events)


async def enroll(session: aiohttp.ClientSession, user_id: int, event_id: int) -> bool:
    async with session.post(
        "https://online.sochisirius.ru/forms?fid=199910202940",
        data={
            "id": event_id,
            "fid": 199910202940,
            "act": "send",
            "__api": 2,
            "f_1032910003": user_id,
            "task": "edit",
        },
    ) as response:
        data = await response.json()
        if "e" in data["enrolled"]:
            return False
        return True


async def wait_enroll(
    register_from: datetime,
    session: aiohttp.ClientSession,
    user_id: int,
    event_id: int,
    name: str,
) -> None:
    await asyncio.sleep((register_from - datetime.now()).total_seconds() - 3)
    num = 1
    while not await enroll(session, user_id, event_id):
        print(f"Error ({num} - {name})")
        num += 1
    print(f"Ok ({num} - {name})")
    await session.close()


async def timer(pool: set[tuple[datetime, str]]) -> None:
    for register_from, name in sorted(pool, key=lambda e: e[0]):
        while register_from - datetime.now() > timedelta(seconds=3):
            print(name, register_from - datetime.now(), end="\r")
            await asyncio.sleep(1)
        await asyncio.sleep(10)


async def main() -> None:
    users: list[tuple[str, str]]
    scheduled_enroll: dict[
        tuple[int, int],
        tuple[datetime, aiohttp.ClientSession, int, int, str],
    ] = {}
    fn = "users.json"

    if not exists(fn):
        users = []
        with open(fn, "w") as file:
            json.dump(users, file)
    else:
        with open(fn) as file:
            users = json.load(file)

    while True:
        print(
            "---",
            *(f"{num} - {ep[0]}" for num, ep in enumerate(users, start=1)),
            "---",
            "A - add user",
            "D - delete user",
            f"S - start enroll timer ({len(scheduled_enroll)})",
            "E - exit",
            "Or number for enroll",
            sep="\n",
        )
        action = input(" -> ")

        if action.lower() == "a":
            email, password = (
                input("Email -> "),
                input("Password -> "),
            )
            users.append((email, password))
            with open(fn, "w") as file:
                json.dump(users, file)
        elif action.lower() == "d":
            users.pop(int(input("Number -> ")))
            with open(fn, "w") as file:
                json.dump(users, file)
        elif action.lower() == "s":
            tasks = [timer({(s[0], s[4]) for s in scheduled_enroll.values()})]
            for (
                register_from,
                session,
                user_id,
                event_id,
                name,
            ) in scheduled_enroll.values():
                tasks.append(
                    wait_enroll(register_from, session, user_id, event_id, name)
                )
            await asyncio.gather(*tasks)
        elif action.lower() == "e":
            for s in scheduled_enroll.values():
                await s[1].close()
            break
        elif action.isnumeric():
            login, password = users[int(action) - 1]
            session = create_user_session(login, password)
            user, raw_events = await get_user_and_events(session)
            user_id = int(user["id"])
            events: list[tuple[int, datetime, str]] = []

            num = 1
            for event in raw_events:
                id = int(event["ids"])
                name = event["enm"]
                start = datetime.strptime(
                    f'{event["db"]} {event["tb"]}', "%d.%m.%Y %H:%M:%S"
                )

                if "regStartDate" not in event:
                    continue

                register_from = start - timedelta(hours=int(event["regStartDate"]))
                register_to = start - timedelta(hours=int(event.get("regEndDate", 0)))
                limit = int(event["peopleLimit"])
                enrolled = int(event["enrolledAll"])
                is_enrolled = bool(event.get("enrolled", 0))

                if (
                    limit == enrolled
                    or is_enrolled
                    or (id, user_id) in scheduled_enroll
                    or register_to < datetime.now()
                    or register_from > (datetime.now() + timedelta(2))
                ):
                    continue

                size = get_terminal_size()
                print(
                    "---",
                    f"{num: <2} - {name[:size.columns-5]}",
                    f"     {start} ({register_from})"
                    if register_from > datetime.now()
                    else f"     {start}",
                    sep="\n",
                )
                events.append((id, register_from, name))
                num += 1

            id, register_from, name = events[int(input("Event -> ")) - 1]
            user_id = int(user["id"])
            if register_from > datetime.now():
                scheduled_enroll[(id, user_id)] = (
                    register_from,
                    session,
                    user_id,
                    id,
                    name,
                )
            else:
                num = 1
                while not await enroll(session, int(user["id"]), id):
                    print(f"Error ({num})")
                    num += 1
                print(f"Ok ({num})")
                await session.close()

        else:
            raise ValueError("Incorrect action")


asyncio.run(main())
