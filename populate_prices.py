import config
import config_polygon
import json
import requests
import datetime, time
import aiohttp, asyncpg, asyncio


#Why binary better than execute many -- 
async def write_to_db(connection, params):
    await connection.copy_records_to_table('stock_price', records=params)
    #await connection.executemany("""
    # INSERT INTO stock_price (stock_id, dt, open, high, low, close, volume) VLAUES ($1, $2, $3, $4, $5, $6, $7)
    #""", params)


async def get_price(pool, stock_id, url):
    try: 
        async with pool.acquire() as connection:
            async with aiohttp.ClientSession() as session:
                async with session.get(url=url) as response:
                    resp = await response.read()
                    response = json.loads(resp)
                    params = [(stock_id, datetime.datetime.fromtimestamp(bar['t'] / 1000.0), round(bar['o'], 2), round(bar['h'], 2), round(bar['l'], 2), round(bar['c'], 2), bar['v']) for bar in response['results']]
                    await write_to_db(connection, params)

    except Exception as e:
        print("Unable to get url {} due to {}.".format(url, e.__class__))


async def get_prices(pool, symbol_urls):
    try:
        # schedule aiohttp requests to run concurrently for all symbols
        ret = await asyncio.gather(*[get_price(pool, stock_id, symbol_urls[stock_id]) for stock_id in symbol_urls])
        print("Finalized all. Returned  list of {} outputs.".format(len(ret)))
    except Exception as e:
        print(e)


async def get_stocks():
    # create database connection pool
    pool = await asyncpg.create_pool(user=config.DB_USER, password=config.DB_PASS, database=config.DB_NAME, host=config.DB_HOST, command_timeout=60)
    
    # get a connection
    async with pool.acquire() as connection:
        stocks = await connection.fetch("SELECT * FROM stock WHERE id IN (SELECT holding_id FROM etf_holding WHERE etf_id=21405)")

        symbol_urls = {}
        for stock in stocks:
            symbol_urls[stock['id']] = f"https://api.polygon.io/v2/aggs/ticker/{stock['symbol']}/range/5/minute/2024-06-01/2024-08-05?apiKey={config_polygon.API_KEY}&limit=1000"

    await get_prices(pool, symbol_urls)


start = time.time()

asyncio.run(get_stocks())

end = time.time()

print("Took {} seconds.".format(end - start))