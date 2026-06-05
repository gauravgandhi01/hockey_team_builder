# Per-Game Dominance Comparison

Scenarios compared against the current shipped model:

- `current_70_30`: current baseline
- `global_60_40`: all positions shifted to 60% totals / 40% rates
- `global_55_45`: all positions shifted to 55% totals / 45% rates
- `global_55_45_sqrt_totals`: 55/45 plus square-root compression on totals metrics before percentile scoring

## 2010s

### Center

| Cur Rank | Player | Team | Cur Score | 60/40 Rank | 60/40 Δ | 55/45 Rank | 55/45 Δ | 55/45 + sqrt Rank | 55/45 + sqrt Δ |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Sidney Crosby | PIT | 99.0 | 1 | +0.0 | 1 | +0.0 | 1 | +0.0 |
| 2 | Steven Stamkos | TBL | 94.6 | 2 | -0.9 | 2 | -1.4 | 2 | -1.4 |
| 3 | Patrice Bergeron | BOS | 94.5 | 3 | -1.4 | 3 | -2.0 | 3 | -2.0 |
| 4 | Evgeni Malkin | PIT | 94.1 | 4 | -1.4 | 6 | -2.3 | 6 | -2.3 |
| 5 | Jonathan Toews | CHI | 93.5 | 5 | -0.9 | 5 | -1.4 | 5 | -1.4 |
| 6 | Anze Kopitar | LAK | 93.4 | 7 | -1.4 | 8 | -1.9 | 8 | -1.9 |
| 7 | John Tavares | NYI | 92.2 | 6 | -0.1 | 4 | -0.1 | 4 | -0.1 |
| 8 | Tyler Seguin | DAL | 91.7 | 8 | +0.2 | 7 | +0.1 | 7 | +0.1 |
| 9 | Joe Pavelski | SJS | 90.9 | 9 | -1.1 | 9 | -1.7 | 9 | -1.7 |
| 10 | Nicklas Backstrom | WSH | 89.7 | 10 | -2.2 | 10 | -3.0 | 10 | -3.0 |

### Winger

| Cur Rank | Player | Team | Cur Score | 60/40 Rank | 60/40 Δ | 55/45 Rank | 55/45 Δ | 55/45 + sqrt Rank | 55/45 + sqrt Δ |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Alex Ovechkin | WSH | 99.0 | 1 | +0.0 | 1 | +0.0 | 1 | +0.0 |
| 2 | Patrick Kane | CHI | 98.5 | 2 | -0.3 | 2 | -0.3 | 2 | -0.3 |
| 3 | Nikita Kucherov | TBL | 94.3 | 3 | -0.2 | 3 | -0.2 | 3 | -0.2 |
| 4 | Jamie Benn | DAL | 93.8 | 4 | -1.2 | 4 | -1.7 | 4 | -1.7 |
| 5 | Corey Perry | ANA | 92.8 | 5 | -1.0 | 6 | -1.4 | 6 | -1.4 |
| 6 | Brad Marchand | BOS | 92.3 | 7 | -1.2 | 8 | -1.9 | 8 | -1.9 |
| 7 | Vladimir Tarasenko | STL | 92.1 | 6 | -0.3 | 5 | -0.5 | 5 | -0.5 |
| 8 | Claude Giroux | PHI | 91.8 | 10 | -1.9 | 10 | -2.8 | 10 | -2.8 |
| 9 | Max Pacioretty | MTL | 91.4 | 9 | -0.8 | 9 | -1.3 | 9 | -1.3 |
| 10 | Blake Wheeler | WPG | 90.9 | 11 | -1.9 | 12 | -2.9 | 12 | -2.9 |

60/40 top-10 entrants/leavers:
- Entrants: David Pastrnak (BOS) #8
- Leavers: Blake Wheeler (WPG)

55/45 top-10 entrants/leavers:
- Entrants: David Pastrnak (BOS) #7
- Leavers: Blake Wheeler (WPG)

55/45 + sqrt top-10 entrants/leavers:
- Entrants: David Pastrnak (BOS) #7
- Leavers: Blake Wheeler (WPG)

### Defenseman

| Cur Rank | Player | Team | Cur Score | 60/40 Rank | 60/40 Δ | 55/45 Rank | 55/45 Δ | 55/45 + sqrt Rank | 55/45 + sqrt Δ |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Erik Karlsson | OTT | 97.3 | 1 | +0.0 | 1 | +0.0 | 1 | +0.0 |
| 2 | Kris Letang | PIT | 95.9 | 2 | +0.0 | 2 | +0.0 | 2 | +0.0 |
| 3 | Brent Burns | SJS | 95.2 | 3 | -0.6 | 3 | -1.1 | 3 | -1.1 |
| 4 | Alex Pietrangelo | STL | 93.9 | 5 | -0.5 | 6 | -0.9 | 6 | -0.9 |
| 5 | Dustin Byfuglien | WPG | 93.9 | 4 | -0.3 | 4 | -0.5 | 4 | -0.5 |
| 6 | John Carlson | WSH | 93.9 | 7 | -0.9 | 7 | -1.3 | 7 | -1.3 |
| 7 | Roman Josi | NSH | 93.4 | 6 | +0.0 | 5 | +0.0 | 5 | +0.0 |
| 8 | Drew Doughty | LAK | 92.0 | 8 | -0.6 | 9 | -1.0 | 9 | -1.0 |
| 9 | Duncan Keith | CHI | 92.0 | 9 | -0.6 | 8 | -0.8 | 8 | -0.8 |
| 10 | Mark Giordano | CGY | 91.9 | 10 | -0.7 | 10 | -1.1 | 10 | -1.1 |

### Goalie

| Cur Rank | Player | Team | Cur Score | 60/40 Rank | 60/40 Δ | 55/45 Rank | 55/45 Δ | 55/45 + sqrt Rank | 55/45 + sqrt Δ |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Tuukka Rask | BOS | 98.2 | 1 | +0.0 | 1 | +0.0 | 1 | +0.0 |
| 2 | Carey Price | MTL | 97.3 | 2 | -2.1 | 2 | -3.1 | 2 | -3.1 |
| 3 | Pekka Rinne | NSH | 97.1 | 3 | -2.5 | 3 | -3.8 | 3 | -3.8 |
| 4 | Henrik Lundqvist | NYR | 91.6 | 5 | -2.7 | 5 | -4.1 | 5 | -4.1 |
| 5 | Sergei Bobrovsky | CBJ | 91.5 | 4 | +0.5 | 4 | +0.8 | 4 | +0.8 |
| 6 | Braden Holtby | WSH | 89.9 | 6 | -3.0 | 6 | -4.5 | 6 | -4.5 |
| 7 | Jonathan Quick | LAK | 86.4 | 8 | -3.9 | 8 | -5.8 | 8 | -5.8 |
| 8 | Marc-Andre Fleury | PIT | 86.1 | 7 | -1.5 | 7 | -2.4 | 7 | -2.4 |
| 9 | Corey Crawford | CHI | 83.0 | 9 | -2.5 | 10 | -3.2 | 10 | -3.2 |
| 10 | Antti Niemi | SJS | 79.5 | 11 | -0.1 | 12 | -0.2 | 12 | -0.2 |

60/40 top-10 entrants/leavers:
- Entrants: Andrei Vasilevskiy (TBL) #10
- Leavers: Antti Niemi (SJS)

55/45 top-10 entrants/leavers:
- Entrants: Brian Elliott (STL) #9
- Leavers: Antti Niemi (SJS)

55/45 + sqrt top-10 entrants/leavers:
- Entrants: Brian Elliott (STL) #9
- Leavers: Antti Niemi (SJS)

## 2020s

### Center

| Cur Rank | Player | Team | Cur Score | 60/40 Rank | 60/40 Δ | 55/45 Rank | 55/45 Δ | 55/45 + sqrt Rank | 55/45 + sqrt Δ |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Connor McDavid | EDM | 99.0 | 2 | -0.3 | 2 | -0.8 | 2 | -0.8 |
| 2 | Leon Draisaitl | EDM | 98.7 | 1 | +0.3 | 1 | +0.3 | 1 | +0.3 |
| 3 | Nathan MacKinnon | COL | 96.8 | 3 | -0.6 | 3 | -1.2 | 3 | -1.2 |
| 4 | Sidney Crosby | PIT | 95.4 | 4 | -0.3 | 4 | -0.8 | 4 | -0.8 |
| 5 | Auston Matthews | TOR | 94.1 | 5 | +0.2 | 5 | -0.1 | 5 | -0.1 |
| 6 | Sebastian Aho | CAR | 90.2 | 7 | -1.2 | 7 | -1.9 | 7 | -1.9 |
| 7 | Aleksander Barkov | FLA | 89.3 | 6 | +0.8 | 6 | +1.3 | 6 | +1.3 |
| 8 | Mark Scheifele | WPG | 88.9 | 8 | -1.6 | 8 | -2.4 | 8 | -2.4 |
| 9 | Mika Zibanejad | NYR | 88.2 | 9 | -1.4 | 9 | -2.4 | 9 | -2.4 |
| 10 | John Tavares | TOR | 87.2 | 10 | -1.2 | 10 | -1.9 | 10 | -1.9 |

### Winger

| Cur Rank | Player | Team | Cur Score | 60/40 Rank | 60/40 Δ | 55/45 Rank | 55/45 Δ | 55/45 + sqrt Rank | 55/45 + sqrt Δ |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | David Pastrnak | BOS | 99.0 | 1 | +0.0 | 1 | +0.0 | 1 | +0.0 |
| 2 | Kirill Kaprizov | MIN | 97.7 | 2 | +0.2 | 2 | +0.2 | 2 | +0.2 |
| 3 | Nikita Kucherov | TBL | 96.6 | 3 | +0.5 | 3 | +0.5 | 3 | +0.5 |
| 4 | Kyle Connor | WPG | 95.5 | 4 | -0.2 | 5 | -0.5 | 5 | -0.5 |
| 5 | Jason Robertson | DAL | 95.0 | 6 | -0.5 | 6 | -0.8 | 6 | -0.8 |
| 6 | Mikko Rantanen | COL | 94.2 | 5 | +0.8 | 4 | +1.1 | 4 | +1.1 |
| 7 | William Nylander | TOR | 94.0 | 8 | -0.6 | 8 | -0.8 | 8 | -0.8 |
| 8 | Alex Ovechkin | WSH | 93.7 | 7 | -0.3 | 7 | -0.5 | 7 | -0.5 |
| 9 | Filip Forsberg | NSH | 92.0 | 9 | -0.1 | 9 | -0.1 | 9 | -0.1 |
| 10 | Artemi Panarin | NYR | 90.0 | 10 | -0.1 | 10 | -0.1 | 10 | -0.1 |

### Defenseman

| Cur Rank | Player | Team | Cur Score | 60/40 Rank | 60/40 Δ | 55/45 Rank | 55/45 Δ | 55/45 + sqrt Rank | 55/45 + sqrt Δ |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Cale Makar | COL | 97.3 | 1 | +0.0 | 1 | +0.0 | 1 | +0.0 |
| 2 | Roman Josi | NSH | 95.9 | 2 | +0.0 | 2 | -0.2 | 2 | -0.2 |
| 3 | Rasmus Dahlin | BUF | 93.2 | 4 | -0.2 | 4 | -0.5 | 4 | -0.5 |
| 4 | Zach Werenski | CBJ | 93.0 | 3 | +0.4 | 3 | +0.6 | 3 | +0.6 |
| 5 | Quinn Hughes | VAN | 92.3 | 5 | +0.3 | 5 | +0.3 | 5 | +0.3 |
| 6 | Victor Hedman | TBL | 91.7 | 6 | -0.5 | 6 | -0.9 | 6 | -0.9 |
| 7 | Adam Fox | NYR | 90.4 | 7 | -0.7 | 8 | -1.2 | 8 | -1.2 |
| 8 | Josh Morrissey | WPG | 89.9 | 9 | -0.7 | 9 | -1.0 | 9 | -1.0 |
| 9 | Miro Heiskanen | DAL | 89.5 | 8 | +0.0 | 7 | +0.0 | 7 | +0.0 |
| 10 | Evan Bouchard | EDM | 87.2 | 12 | -1.7 | 12 | -2.5 | 12 | -2.5 |

60/40 top-10 entrants/leavers:
- Entrants: John Carlson (WSH) #10
- Leavers: Evan Bouchard (EDM)

55/45 top-10 entrants/leavers:
- Entrants: John Carlson (WSH) #10
- Leavers: Evan Bouchard (EDM)

55/45 + sqrt top-10 entrants/leavers:
- Entrants: John Carlson (WSH) #10
- Leavers: Evan Bouchard (EDM)

### Goalie

| Cur Rank | Player | Team | Cur Score | 60/40 Rank | 60/40 Δ | 55/45 Rank | 55/45 Δ | 55/45 + sqrt Rank | 55/45 + sqrt Δ |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Andrei Vasilevskiy | TBL | 98.2 | 1 | +0.0 | 1 | +0.0 | 1 | +0.0 |
| 2 | Connor Hellebuyck | WPG | 95.8 | 2 | -1.0 | 2 | -1.5 | 2 | -1.5 |
| 3 | Igor Shesterkin | NYR | 92.4 | 3 | +0.1 | 3 | +0.2 | 3 | +0.2 |
| 4 | Jake Oettinger | DAL | 88.9 | 4 | -1.0 | 4 | -1.6 | 4 | -1.6 |
| 5 | Ilya Sorokin | NYI | 87.2 | 5 | -1.4 | 5 | -2.0 | 5 | -2.0 |
| 6 | Sergei Bobrovsky | FLA | 82.2 | 7 | -2.5 | 7 | -3.1 | 7 | -3.1 |
| 7 | Jeremy Swayman | BOS | 81.1 | 6 | -0.9 | 6 | -1.2 | 6 | -1.2 |
| 8 | Juuse Saros | NSH | 79.4 | 8 | -0.8 | 9 | -1.2 | 9 | -1.2 |
| 9 | Filip Gustavsson | MIN | 78.3 | 9 | +0.1 | 8 | +0.2 | 8 | +0.2 |
| 10 | Tristan Jarry | PIT | 78.2 | 10 | -0.6 | 10 | -0.9 | 10 | -0.9 |

