import asyncio
import datetime
import os
from datetime import timedelta

import aiosqlite
import discord
from dotenv import load_dotenv

load_dotenv()

class MessageOrm:
    database: aiosqlite.Connection

    def __init__(self, mess_id: int, channel_id: int, created_at: str, database: aiosqlite.Connection):
        self.mess_id = mess_id
        self.channel_id = channel_id
        self.created_at = datetime.datetime.fromisoformat(created_at)
        self.database = database

    async def delete(self):
        async with self.database.execute(
            'DELETE FROM messages WHERE mess_id = ?',
            (self.mess_id,)
        ) as cursor:
            await self.database.commit()
            return cursor.rowcount

class Bot(discord.Client):

    def __init__(self):
        super().__init__()
        self.sqlite = None

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        messages = await self.fetch_messages()
        for message in messages:
            asyncio.create_task(self.clean_up(message))

    async def on_message(self, message: discord.Message):
        if message.author.id != self.user.id:
            return

        if message.content.startswith('ndl!'):
            await message.edit(content=message.content[4:])
            return

        orm_obj = await self.save_message(message)
        asyncio.create_task(self.clean_up(orm_obj))


    async def clean_up(self, orm_obj: MessageOrm):
        await discord.utils.sleep_until(orm_obj.created_at + timedelta(minutes=5))
        channel = self.get_channel(orm_obj.channel_id)
        if not channel:
            await orm_obj.delete()
            return
        try:
            message = await channel.fetch_message(orm_obj.mess_id)
            await message.delete()
        except discord.NotFound or discord.Forbidden:
            pass
        await orm_obj.delete()

    async def save_message(self, message: discord.Message):
        async with self.sqlite.execute(
            'INSERT INTO messages (mess_id, channel_id, created_at) VALUES (?, ?, ?)',
            (message.id, message.channel.id, message.created_at)
        ) as cursor:
            await self.sqlite.commit()
            return MessageOrm(
                mess_id=message.id,
                channel_id=message.channel.id,
                created_at=str(message.created_at),
                database=self.sqlite
            )

    async def fetch_messages(self):
        async with self.sqlite.execute(
            'SELECT * FROM messages'
        ) as cursor:
            rows = await cursor.fetchall()
            return [MessageOrm(*row, database=self.sqlite) for row in rows]


    async def setup_hook(self) -> None:
        self.sqlite = await aiosqlite.connect('db.sqlite')
        await self.sqlite.execute(
            'CREATE TABLE IF NOT EXISTS messages (mess_id INTEGER PRIMARY KEY, channel_id INTEGER, created_at TEXT)'
        )


client = Bot()
client.run(os.getenv('DISCORD_TOKEN'))
