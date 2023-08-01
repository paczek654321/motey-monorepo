import aiohttp
from aiohttp import web
import aiohttp_jinja2
import aiohttp_session

from sqlalchemy import insert, select, update, exists
from sqlalchemy.orm import Session

from motey.infrastructure.database.storage import EmoteStorage, UserStorage
from motey.infrastructure.filesystem import EmoteFileWriter
from motey.infrastructure.database.tables import User, Server, Emote, users_servers_association_table

from motey.infrastructure.config import Config

routes = web.RouteTableDef()

@aiohttp_jinja2.template('list.html')
async def list_emotes(request: web.Request):
    emotes_list = EmoteStorage(request.app['db']).fetch_all_emotes()
    emotes = []
    usernames = {}
    for emote in emotes_list:
        emotes.append(emote[0])
        usernames[emote[0].name] = emote[1]
    return {"emotes": emotes, "usernames": usernames}


@aiohttp_jinja2.template('index.html')
async def index(request: web.Request):
    return None


@aiohttp_jinja2.template('index.html')
async def process_upload(request: web.Request):
    data = await request.post()
    emote = data['emote']
    emote_name = data['emotename']
    session = await aiohttp_session.get_session(request)
    if not emote_name:
        return {'error_message': 'Please enter emote name'}

    file_writer = EmoteFileWriter(emote_name, emote.filename, emote.file)
    if file_writer.extension_valid:
        file_writer.save_to_filesystem()
    else:
        return {'error_message': 'File extension invalid'}

    with Session(request.app['db']) as db_session:
        stmt = select(User).where(User.discord_id==session['discord_id'])
        author = db_session.scalars(stmt).one()
    emote_storage = EmoteStorage(request.app['db'])
    if emote_storage.emote_exists(emote_name):
        return {'error_message': 'Emote with this name already exists'}
    emote_storage.add_emote(emote_name, str(file_writer.path), author)

    raise web.HTTPFound(location='/')


@routes.get('/process_oauth')
async def process_oauth(request: web.Request):
    code = request.rel_url.query.get("code", "")
    session = await aiohttp_session.get_session(request)
    if not code:
        return {'error_message': 'There is no oauth code'}
    payload = {
            "code": str(code),
            "client_id": str(Config.client_id),
            "client_secret": Config.client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": Config.redirect_url,
            "scope": "identify%20guilds"
        }
    async with aiohttp.ClientSession() as client_session:
        async with client_session.post("https://discord.com/api/oauth2/token", data=payload) as response:
            auth_token_data = await response.json()
    access_token = auth_token_data["access_token"]
    header = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }  
    async with aiohttp.ClientSession(headers=header) as client_session:
        async with client_session.get("https://discord.com/api/users/@me") as response:
            user_data = await response.json()
            session['discord_id'] = int(user_data['id'])
    async with aiohttp.ClientSession(headers=header) as client_session:
        async with client_session.get("https://discord.com/api/users/@me/guilds") as response:
            guilds = await response.json()
    with Session(request.app['db']) as db_session:
        if not db_session.query(exists().where(User.discord_id == session['discord_id'])).scalar():
            user = User(discord_id=session['discord_id'], name=user_data["global_name"])
            db_session.add(user)
            db_session.commit()
        stmt = select(User).where(User.discord_id == session['discord_id'])
        user = db_session.scalars(stmt)
        for guild in guilds:
            #add name updating in existing guilds
            guild_id = int(guild["id"])
            guild_name = guild["name"]
            if not db_session.query(exists().where(Server.guild == guild_id)).scalar():
                server = Server(guild=guild_id, name=guild_name)
                db_session.add(server)
                db_session.commit()
            if not db_session.query(exists().where(Server.guild == guild_id, Server.server_users.any(discord_id=session['discord_id']))).scalar():
                user = db_session.query(User).filter_by(discord_id=session['discord_id']).first()
                server = db_session.query(Server).filter_by(guild=guild_id).first()
                server.server_users.append(user)
                db_session.commit()
    raise web.HTTPFound(location='/')
