import asyncio
import types
import pytest

from src.conditor.core.executor.discord_handler import make_discord_handler
from src.conditor.core.planner.models import BuildStep, StepType


class FakeObj:
    def __init__(self, name, oid):
        self.name = name
        self.id = oid


class FakeChannel(FakeObj):
    def __init__(self, name, oid):
        super().__init__(name, oid)
        self._webhooks = []

    async def send(self, content):
        return types.SimpleNamespace(id=9999, content=content)

    async def webhooks(self):
        return self._webhooks


class FakeGuild:
    def __init__(self, gid=1):
        self.id = gid
        self.roles = []
        self.categories = []
        self.text_channels = []
        import asyncio
        import types
        import pytest

        from src.conditor.core.executor.discord_handler import make_discord_handler
        from src.conditor.core.planner.models import BuildStep, StepType


        class FakeObj:
            def __init__(self, name, oid):
                self.name = name
                self.id = oid


        class FakeChannel(FakeObj):
            def __init__(self, name, oid):
                super().__init__(name, oid)
                self._webhooks = []

            async def send(self, content):
                return types.SimpleNamespace(id=9999, content=content)

            async def webhooks(self):
                return self._webhooks


        class FakeGuild:
            def __init__(self, gid=1):
                self.id = gid
                self.roles = []
                self.categories = []
                self.text_channels = []
                self.channels = []

            async def create_role(self, **kwargs):
                r = FakeObj(kwargs.get('name'), 1000 + len(self.roles))
                self.roles.append(r)
                return r

            async def create_category(self, name):
                c = FakeObj(name, 2000 + len(self.categories))
                self.categories.append(c)
                return c

            async def create_text_channel(self, name, category=None, news=False):
                ch = FakeChannel(name, 3000 + len(self.channels))
                self.channels.append(ch)
                self.text_channels.append(ch)
                return ch


        @pytest.mark.asyncio
        async def test_discord_handler_creates_and_resolves(monkeypatch):
            guild = FakeGuild(gid=42)

            # monkeypatch run_with_rate_limit to just call the coroutine
            async def _run(gid, func, *args, **kwargs):
                # func may be a coroutine function
                res = func()
                if asyncio.iscoroutine(res):
                    return await res
                return res

            monkeypatch.setattr('src.conditor.core.executor.discord_handler.run_with_rate_limit', _run)
            # monkeypatch apply_channel_overwrites to noop
            monkeypatch.setattr('src.conditor.core.executor.discord_handler.apply_channel_overwrites', lambda g, c, o: None)

            handler = make_discord_handler(None, guild)

            # create role
            step_role = BuildStep(id='s-role', type=StepType.CREATE_ROLE, payload={'name': 'Admins', 'color': '#ff0000'})
            rres = await handler(step_role)
            assert rres.get('role_id') is not None

            # create category
            step_cat = BuildStep(id='s-cat', type=StepType.CREATE_CATEGORY, payload={'name': 'Community'})
            cres = await handler(step_cat)
            assert cres.get('category_id') is not None

            # create channel referencing the category by step id
            step_chan = BuildStep(id='s-chan', type=StepType.CREATE_CHANNEL, payload={'name': 'general', 'category': 's-cat'})
            chres = await handler(step_chan)
            assert chres.get('channel_id') is not None

            # post message referencing channel by step id
            step_msg = BuildStep(id='s-msg', type=StepType.POST_MESSAGE, payload={'channel': 's-chan', 'content': 'hello'})
            mres = await handler(step_msg)
            assert mres.get('message_id') is not None or mres.get('ok') is not False
