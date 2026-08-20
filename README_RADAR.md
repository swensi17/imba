# Imba Radar

Минутный GitHub-радар: находит имбу, делает аккуратные карточки с превью и пушит в тематические ветки.

## Ветки

| Ветка | Смысл |
|---|---|
| `imba/hot` | вирус / резкий рост |
| `imba/new` | свежие репы |
| `imba/ai` | LLM / agents / MCP |
| `imba/bots` | Telegram / Discord |
| `imba/tools` | CLI / DX |
| `imba/releases` | релизы |
| `imba/latest` | общая лента |

`main` только код.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env   # впиши GITHUB_TOKEN
python -m imba_radar.app bootstrap
python -m imba_radar.app run
```

## PM2

```bash
pm2 start "python -m imba_radar.app run" --name imba-radar --cwd /root/imba-radar
```
