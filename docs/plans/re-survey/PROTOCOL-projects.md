# Projects protocol: GUI save, open and browser search (Block E, areas 20 and 22)

One sitting, about 10 min per app. It fills the two rows headless tools cannot reach: how long a real project
takes to save and open in each app's window, and how long the library browser takes to answer a search.

```
load-32 and load-128 ──► save ──► quit ──► reopen ──► note seconds
                                                     └──► type a search ──► note seconds to first result
```

## Rules

| Rule | Why |
|---|---|
| Use the `load-32` and `load-128` projects from `PROTOCOL-load.md` (Infinite: its own 32- and 128-node patch; the headless side is `project_bench.py infinite --sizes 32,128`) | no second template to build; two sizes show how time grows |
| Time with the phone stopwatch, start on the keypress, stop when the window is usable (play works) | same end point in every app |
| Three runs each, report all three, first run cold (just after a restart) | cold and warm differ by several times |
| Search term: `bass`, typed in one go | every library has it |
| Do not quit an app you did not start for this | owner's rule |

## Per app

| App | Save | Open | Search |
|---|---|---|---|
| Infinite | Cmd+S, note the size on disk | File > Open on the same file | the library panel's search box |
| Live | Cmd+S as a Live Set | double-click the `.als` | the browser's search field |
| Logic | Cmd+S as a project folder | open the `.logicx` | the Library search |
| Bitwig | Cmd+S | open the `.bwproject` | the browser's search field |

## Read-out

Tell Claude "Live: save 1.9 s, 2.1 s, 1.8 s; open 6.4 s cold; search 0.3 s, file 4.2 MB". Claude adds a
GUI row to `dossiers/E.md` section 5 next to the headless numbers, and checks that Infinite's open time
stays close to the headless `--validate` floor (0.76 s) plus its own first-frame time.
