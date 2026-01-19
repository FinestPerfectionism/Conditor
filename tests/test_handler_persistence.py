import asyncio
import json
from pathlib import Path
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
        return type('M', (), {'id': 9999, 'content': content})()

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
        import asyncio
        import json
        from pathlib import Path
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
                return type('M', (), {'id': 9999, 'content': content})()

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
        async def test_handler_persists_mapping(tmp_path, monkeypatch):
            guild = FakeGuild(gid=1234)

            # monkeypatch run_with_rate_limit to just call the coroutine
            async def _run(gid, func, *args, **kwargs):
                res = func()
                if asyncio.iscoroutine(res):
                    return await res
                return res

            monkeypatch.setattr('src.conditor.core.executor.discord_handler.run_with_rate_limit', _run)
            monkeypatch.setattr('src.conditor.core.executor.discord_handler.apply_channel_overwrites', lambda g, c, o: None)

            storage_dir = tmp_path / 'runtime'

            handler1 = make_discord_handler(None, guild, storage_dir=storage_dir)

            # create role with handler1
            step_role = BuildStep(id='s-role', type=StepType.CREATE_ROLE, payload={'name': 'Admins', 'color': '#ff0000'})
            rres = await handler1(step_role)
            assert rres.get('role_id') is not None
            assert len(guild.roles) == 1

            # verify map file exists and contains mapping
            mapf = storage_dir / f'resource_map_{guild.id}.json'
            assert mapf.exists()
            data = json.loads(mapf.read_text(encoding='utf-8'))
            assert 's-role' in data.get('roles', {})

            # create a new handler instance that should read persisted mapping
            handler2 = make_discord_handler(None, guild, storage_dir=storage_dir)

            # calling the same CREATE_ROLE step again should not create another role
            rres2 = await handler2(step_role)
            assert rres2.get('role_id') == rres.get('role_id')
            assert len(guild.roles) == 1

            # create category then channel referencing category by step id via handler1
            step_cat = BuildStep(id='s-cat', type=StepType.CREATE_CATEGORY, payload={'name': 'Community'})
            cres = await handler1(step_cat)
            assert cres.get('category_id') is not None

            step_chan = BuildStep(id='s-chan', type=StepType.CREATE_CHANNEL, payload={'name': 'general', 'category': 's-cat'})
            chres = await handler1(step_chan)
            assert chres.get('channel_id') is not None

            # handler2 should be able to create a message referencing channel by step id without recreating channel
            step_msg = BuildStep(id='s-msg', type=StepType.POST_MESSAGE, payload={'channel': 's-chan', 'content': 'hello'})
            mres = await handler2(step_msg)
            assert mres.get('message_id') is not None


        @pytest.mark.asyncio
        async def test_handler_namespace(tmp_path, monkeypatch):
            guild = FakeGuild(gid=777)
            async def _run(gid, func, *args, **kwargs):
                res = func()
                if asyncio.iscoroutine(res):
                    return await res
                return res
            monkeypatch.setattr('src.conditor.core.executor.discord_handler.run_with_rate_limit', _run)
            monkeypatch.setattr('src.conditor.core.executor.discord_handler.apply_channel_overwrites', lambda g, c, o: None)

            storage_dir = tmp_path / 'runtime'
            # use a namespace
            handler_ns = make_discord_handler(None, guild, storage_dir=storage_dir, namespace='plan-A')
            step_role = BuildStep(id='s-role-ns', type=StepType.CREATE_ROLE, payload={'name': 'NsRole'})
            r = await handler_ns(step_role)
            # check namespaced file exists
            mapf = storage_dir / f'resource_map_{guild.id}_plan-A.json'
            assert mapf.exists()
