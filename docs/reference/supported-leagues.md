---
title: Supported Leagues
parent: Technical Reference
nav_order: 1
---

# Supported Sports & Leagues

Teamarr supports a wide range of sports leagues through multiple data providers.

## Data Providers

| Provider | Description |
|----------|-------------|
| **ESPN** | Primary provider for most US leagues and international soccer |
| **TheSportsDB** | Australian sports, rugby, cricket teams, boxing |
| **HockeyTech** | Canadian and US junior/minor hockey leagues |
| **Cricbuzz** | Cricket schedules (fallback for TSDB cricket) |

---

## Football

| League | ID | Provider |
|--------|-----|----------|
| National Football League | `nfl` | ESPN |
| NCAA Football | `ncaaf` | ESPN |
| United Football League | `ufl` | ESPN |

---

## Basketball

| League | ID | Provider |
|--------|-----|----------|
| National Basketball Association | `nba` | ESPN |
| NBA G League | `nbag` | ESPN |
| Women's National Basketball Association | `wnba` | ESPN |
| NCAA Men's Basketball | `ncaam` | ESPN |
| NCAA Women's Basketball | `ncaaw` | ESPN |
| Unrivaled | `unrivaled` | TSDB |

---

## Hockey

### NHL & NCAA

| League | ID | Provider |
|--------|-----|----------|
| National Hockey League | `nhl` | ESPN |
| NCAA Men's Ice Hockey | `ncaah` | ESPN |
| NCAA Women's Ice Hockey | `ncaawh` | ESPN |

### Canadian Major Junior (CHL)

| League | ID | Provider |
|--------|-----|----------|
| Canadian Hockey League | `chl` | HockeyTech |
| Ontario Hockey League | `ohl` | HockeyTech |
| Western Hockey League | `whl` | HockeyTech |
| Quebec Major Junior Hockey League | `qmjhl` | HockeyTech |

### Pro/Minor Pro

| League | ID | Provider |
|--------|-----|----------|
| American Hockey League | `ahl` | HockeyTech |
| East Coast Hockey League | `echl` | HockeyTech |
| Professional Women's Hockey League | `pwhl` | HockeyTech |

### US Junior

| League | ID | Provider |
|--------|-----|----------|
| United States Hockey League | `ushl` | HockeyTech |

### Canadian Junior A

| League | ID | Provider |
|--------|-----|----------|
| Ontario Junior Hockey League | `ojhl` | HockeyTech |
| British Columbia Hockey League | `bchl` | HockeyTech |
| Saskatchewan Junior Hockey League | `sjhl` | HockeyTech |
| Alberta Junior Hockey League | `ajhl` | HockeyTech |
| Manitoba Junior Hockey League | `mjhl` | HockeyTech |
| Maritime Junior Hockey League | `mhl` | HockeyTech |

### European

| League | ID | Provider |
|--------|-----|----------|
| Norwegian Fjordkraft-ligaen | `norwegian-hockey` | TSDB |

---

## Baseball & Softball

| League | ID | Provider |
|--------|-----|----------|
| Major League Baseball | `mlb` | ESPN |
| NCAA Baseball | `ncaabb` | ESPN |
| NCAA Softball | `ncaasbw` | ESPN |

---

## Soccer

### North America

| League | ID | Provider |
|--------|-----|----------|
| Major League Soccer | `mls` | ESPN |
| National Women's Soccer League | `nwsl` | ESPN |
| NCAA Men's Soccer | `ncaas` | ESPN |
| NCAA Women's Soccer | `ncaaws` | ESPN |
| Liga MX | `ligamx` | ESPN |

### England

| League | ID | Provider |
|--------|-----|----------|
| English Premier League | `epl` | ESPN |
| EFL Championship | `championship` | ESPN |
| EFL League One | `league-one` | ESPN |
| EFL League Two | `league-two` | ESPN |
| FA Cup | `fa-cup` | ESPN |
| EFL Cup (Carabao Cup) | `league-cup` | ESPN |

### Europe - Top Leagues

| League | ID | Provider |
|--------|-----|----------|
| La Liga (Spain) | `laliga` | ESPN |
| Copa del Rey | `copa-del-rey` | ESPN |
| Bundesliga (Germany) | `bundesliga` | ESPN |
| DFB-Pokal | `dfb-pokal` | ESPN |
| Serie A (Italy) | `seriea` | ESPN |
| Coppa Italia | `coppa-italia` | ESPN |
| Ligue 1 (France) | `ligue1` | ESPN |
| Coupe de France | `coupe-de-france` | ESPN |
| Eredivisie (Netherlands) | `eredivisie` | ESPN |
| Primeira Liga (Portugal) | `primeira` | ESPN |
| Belgian Pro League | `jupiler` | ESPN |
| Scottish Premiership | `spfl` | ESPN |
| Turkish Süper Lig | `super-lig` | ESPN |
| Greek Super League | `greek-super-league` | ESPN |
| Saudi Pro League | `spl` | ESPN |

### UEFA Competitions

| League | ID | Provider |
|--------|-----|----------|
| UEFA Champions League | `ucl` | ESPN |
| UEFA Europa League | `uel` | ESPN |
| UEFA Europa Conference League | `uecl` | ESPN |

### South America

| League | ID | Provider |
|--------|-----|----------|
| Argentine Liga Profesional | `lpa` | ESPN |
| Brazilian Serie A | `brasileirao` | ESPN |
| Colombian Primera A | `dimayor` | ESPN |
| Copa Libertadores | `libertadores` | ESPN |
| Copa Sudamericana | `sudamericana` | ESPN |

### International

| League | ID | Provider |
|--------|-----|----------|
| FIFA World Cup | `world-cup` | ESPN |
| FIFA Women's World Cup | `wwc` | ESPN |
| UEFA European Championship | `euro` | ESPN |
| Copa America | `copa-america` | ESPN |
| CONCACAF Gold Cup | `gold-cup` | ESPN |
| CONCACAF Nations League | `cnl` | ESPN |

### Asia/Pacific

| League | ID | Provider |
|--------|-----|----------|
| J1 League (Japan) | `jleague` | ESPN |
| A-League Men (Australia) | `aleague` | ESPN |

---

## Combat Sports

| League | ID | Provider | Type |
|--------|-----|----------|------|
| Ultimate Fighting Championship | `ufc` | ESPN | Event Card |
| Boxing | `boxing` | TSDB | Event Card |

{: .note }
Combat sports use "Event Card" matching rather than team vs team matching.

---

## Cricket

| League | ID | Provider | Fallback |
|--------|-----|----------|----------|
| Indian Premier League | `ipl` | TSDB | Cricbuzz |
| Big Bash League | `bbl` | TSDB | Cricbuzz |
| SA20 | `sa20` | TSDB | Cricbuzz |

{: .note }
Cricket uses TSDB for team data and Cricbuzz as a fallback for schedules.

---

## Rugby

| League | ID | Provider |
|--------|-----|----------|
| National Rugby League (Australia) | `nrl` | TSDB |
| Super Rugby Pacific | `super-rugby` | TSDB |

---

## Australian Football

| League | ID | Provider |
|--------|-----|----------|
| Australian Football League | `afl` | TSDB |

---

## Lacrosse

| League | ID | Provider |
|--------|-----|----------|
| National Lacrosse League | `nll` | ESPN |
| Premier Lacrosse League | `pll` | ESPN |
| NCAA Men's Lacrosse | `ncaalax` | ESPN |
| NCAA Women's Lacrosse | `ncaawlax` | ESPN |

---

## Volleyball

| League | ID | Provider |
|--------|-----|----------|
| NCAA Men's Volleyball | `ncaavb` | ESPN |
| NCAA Women's Volleyball | `ncaawvb` | ESPN |

---

## Adding New Leagues

New leagues are added directly to the database schema. If you need a league that isn't listed here, please open an issue on [GitHub](https://github.com/Pharaoh-Labs/teamarr/issues).
