# First-Principles Architectural Blueprints (from build-your-own-x)

This distilled knowledge base grounds the Semi-Brain in canonical, from-scratch systems engineering across Infinite's primary technical domains.

---

## 🏗 Domain: 3D Renderer (11 Canonical Blueprints)

### Core Architectural Invariants:
- **Pipeline Order**: Local Space -> World Matrix -> View Transform -> Projection Matrix -> Viewport Rasterization.
- **Depth & Shading Invariant**: Perspective-correct interpolation of barycentric UVs and normals; depth buffer monotonic z-sorting.

### Reference Blueprints:
- **[C++]** **C++**: _Introduction to Ray Tracing: a Simple Method for Creating 3D Images_ — `https://www.scratchapixel.com/lessons/3d-basic-rendering/introduction-to-ray-tracing/how-does-it-work`
- **[C++]** **C++**: _How OpenGL works: software rendering in 500 lines of code_ — `https://github.com/ssloy/tinyrenderer/wiki`
- **[C++]** **C++**: _Raycasting engine of Wolfenstein 3D_ — `http://lodev.org/cgtutor/raycasting.html`
- **[C++]** **C++**: _Physically Based Rendering:From Theory To Implementation_ — `http://www.pbr-book.org/`
- **[C++]** **C++**: _Ray Tracing in One Weekend_ — `https://raytracing.github.io/books/RayTracingInOneWeekend.html`
- **[C++]** **C++**: _Rasterization: a Practical Implementation_ — `https://www.scratchapixel.com/lessons/3d-basic-rendering/rasterization-practical-implementation/overview-rasterization-algorithm`
- **[C# / TypeScript / JavaScript]** **C# / TypeScript / JavaScript**: _Learning how to write a 3D soft engine from scratch in C#, TypeScript or JavaScript_ — `https://www.davrous.com/2013/06/13/tutorial-series-learning-how-to-write-a-3d-soft-engine-from-scratch-in-c-typescript-or-javascript/`
- **[Java / JavaScript]** **Java / JavaScript**: _Build your own 3D renderer_ — `https://avik-das.github.io/build-your-own-raytracer/`

---

## 🏗 Domain: Command-Line Tool (9 Canonical Blueprints)

### Core Architectural Invariants:
- **Minimal Zero-Framework Architecture**: Explicit memory ownership, deterministic tick update, clear dataflow.

### Reference Blueprints:
- **[Go]** **Go**: _Visualize your local git contributions with Go_ — `https://flaviocopes.com/go-git-contributions/`
- **[Go]** **Go**: _Build a command line app with Go: lolcat_ — `https://flaviocopes.com/go-tutorial-lolcat/`
- **[Go]** **Go**: _Building a cli command with Go: cowsay_ — `https://flaviocopes.com/go-tutorial-cowsay/`
- **[Go]** **Go**: _Go CLI tutorial: fortune clone_ — `https://flaviocopes.com/go-tutorial-fortune/`
- **[Nim]** **Nim**: _Writing a stow alternative to manage dotfiles_ — `https://xmonader.github.io/nimdays/day06_nistow.html`
- **[Node.js]** **Node.js**: _Create a CLI tool in Javascript_ — `https://citw.dev/tutorial/create-your-own-cli-tool`
- **[Rust]** **Rust**: _Command line apps in Rust_ — `https://rust-cli.github.io/book/index.html`
- **[Rust]** **Rust**: _Writing a Command Line Tool in Rust_ — `https://mattgathu.dev/2017/08/29/writing-cli-app-rust.html`

---

## 🏗 Domain: Emulator / Virtual Machine (13 Canonical Blueprints)

### Core Architectural Invariants:
- **Compilation Pipeline**: Lexer (Token Stream) -> Parser (AST) -> Type Checker / Domain Inference -> Typed IR -> Target Code (GLSL / Bytecode).

### Reference Blueprints:
- **[C]** **C**: _Home-grown bytecode interpreters_ — `https://medium.com/bumble-tech/home-grown-bytecode-interpreters-51e12d59b25c`
- **[C]** **C**: _Virtual machine in C_ — `http://web.archive.org/web/20200121100942/https://blog.felixangell.com/virtual-machine-in-c/`
- **[C]** **C**: _Write your Own Virtual Machine_ — `https://justinmeiners.github.io/lc3-vm/`
- **[C]** **C**: _Writing a Game Boy emulator, Cinoop_ — `https://cturt.github.io/cinoop.html`
- **[C++]** **C++**: _How to write an emulator (CHIP-8 interpreter)_ — `http://www.multigesture.net/articles/how-to-write-an-emulator-chip-8-interpreter/`
- **[C++]** **C++**: _Emulation tutorial (CHIP-8 interpreter)_ — `http://www.codeslinger.co.uk/pages/projects/chip8.html`
- **[C++]** **C++**: _Emulation tutorial (GameBoy emulator)_ — `http://www.codeslinger.co.uk/pages/projects/gameboy.html`
- **[C++]** **C++**: _Emulation tutorial (Master System emulator)_ — `http://www.codeslinger.co.uk/pages/projects/mastersystem/memory.html`

---

## 🏗 Domain: Game (34 Canonical Blueprints)

### Core Architectural Invariants:
- **Minimal Zero-Framework Architecture**: Explicit memory ownership, deterministic tick update, clear dataflow.

### Reference Blueprints:
- **[C]** **C**: _Handmade Hero_ — `https://handmadehero.org/`
- **[C]** **C**: _How to Program an NES game in C_ — `https://nesdoug.com/`
- **[C]** **C**: _Chess Engine In C_ — `https://www.youtube.com/playlist?list=PLZ1QII7yudbc-Ky058TEaOstZHVbT-2hg`
- **[C]** **C**: _Let's Make: Dangerous Dave_ — `https://www.youtube.com/playlist?list=PLSkJey49cOgTSj465v2KbLZ7LMn10bCF9`
- **[C]** **C**: _Learn Video Game Programming in C_ — `https://www.youtube.com/playlist?list=PLT6WFYYZE6uLMcPGS3qfpYm7T_gViYMMt`
- **[C]** **C**: _Coding A Sudoku Solver in C_ — `https://www.youtube.com/playlist?list=PLkTXsX7igf8edTYU92nU-f5Ntzuf-RKvW`
- **[C]** **C**: _Coding a Rogue/Nethack RPG in C_ — `https://www.youtube.com/playlist?list=PLkTXsX7igf8erbWGYT4iSAhpnJLJ0Nk5G`
- **[C]** **C**: _On Tetris and Reimplementation_ — `https://brennan.io/2015/06/12/tetris-reimplementation/`

---

## 🏗 Domain: Git (7 Canonical Blueprints)

### Core Architectural Invariants:
- **DAG & Object Model**: Immutable content-addressed blobs, trees, and commit DAG; monotonic state transitions.

### Reference Blueprints:
- **[Haskell]** **Haskell**: _Reimplementing “git clone” in Haskell from the bottom up_ — `http://stefan.saasen.me/articles/git-clone-in-haskell-from-the-bottom-up/`
- **[JavaScript]** **JavaScript**: _Gitlet_ — `http://gitlet.maryrosecook.com/docs/gitlet.html`
- **[JavaScript]** **JavaScript**: _Build GIT - Learn GIT_ — `https://kushagra.dev/blog/build-git-learn-git/`
- **[Python]** **Python**: _Just enough of a Git client to create a repo, commit, and push itself to GitHub_ — `https://benhoyt.com/writings/pygit/`
- **[Python]** **Python**: _Write yourself a Git!_ — `https://wyag.thb.lt/`
- **[Python]** **Python**: _ugit: Learn Git Internals by Building Git Yourself_ — `https://www.leshenko.net/p/ugit/`
- **[Ruby]** **Ruby**: _Rebuilding Git in Ruby_ — `https://robots.thoughtbot.com/rebuilding-git-in-ruby`

---

## 🏗 Domain: Operating System (19 Canonical Blueprints)

### Core Architectural Invariants:
- **Minimal Zero-Framework Architecture**: Explicit memory ownership, deterministic tick update, clear dataflow.

### Reference Blueprints:
- **[Assembly]** **Assembly**: _Writing a Tiny x86 Bootloader_ — `http://joebergeron.io/posts/post_two.html`
- **[Assembly]** **Assembly**: _Baking Pi – Operating Systems Development_ — `http://www.cl.cam.ac.uk/projects/raspberrypi/tutorials/os/index.html`
- **[C]** **C**: _Building a software and hardware stack for a simple computer from scratch_ — `https://www.youtube.com/watch?v=ZjwvMcP3Nf0&list=PLU94OURih-CiP4WxKSMt3UcwMSDM3aTtX`
- **[C]** **C**: _Operating Systems: From 0 to 1_ — `https://tuhdo.github.io/os01/`
- **[C]** **C**: _The little book about OS development_ — `https://littleosbook.github.io/`
- **[C]** **C**: _Roll your own toy UNIX-clone OS_ — `http://jamesmolloy.co.uk/tutorial_html/`
- **[C]** **C**: _Kernel 101 – Let’s write a Kernel_ — `https://arjunsreedharan.org/post/82710718100/kernel-101-lets-write-a-kernel`
- **[C]** **C**: _Kernel 201 – Let’s write a Kernel with keyboard and screen support_ — `https://arjunsreedharan.org/post/99370248137/kernel-201-lets-write-a-kernel-with-keyboard`

---

## 🏗 Domain: Physics Engine (7 Canonical Blueprints)

### Core Architectural Invariants:
- **Minimal Zero-Framework Architecture**: Explicit memory ownership, deterministic tick update, clear dataflow.

### Reference Blueprints:
- **[C]** **C**: _Video Game Physics Tutorial_ — `https://www.toptal.com/game/video-game-physics-part-i-an-introduction-to-rigid-body-dynamics`
- **[C++]** **C++**: _Game physics series by Allen Chou_ — `http://allenchou.net/game-physics-series/`
- **[C++]** **C++**: _How to Create a Custom Physics Engine_ — `https://gamedevelopment.tutsplus.com/series/how-to-create-a-custom-physics-engine--gamedev-12715`
- **[C++]** **C++**: _3D Physics Engine Tutorial_ — `https://www.youtube.com/playlist?list=PLEETnX-uPtBXm1KEr_2zQ6K_0hoGH6JJ0`
- **[JavaScript]** **JavaScript**: _How Physics Engines Work_ — `http://buildnewgames.com/gamephysics/`
- **[JavaScript]** **JavaScript**: _Broad Phase Collision Detection Using Spatial Partitioning_ — `http://buildnewgames.com/broad-phase-collision-detection/`
- **[JavaScript]** **JavaScript**: _Build a simple 2D physics engine for JavaScript games_ — `https://developer.ibm.com/tutorials/wa-build2dphysicsengine/?mhsrc=ibmsearch_a&mhq=2dphysic`

---

## 🏗 Domain: Programming Language (41 Canonical Blueprints)

### Core Architectural Invariants:
- **Compilation Pipeline**: Lexer (Token Stream) -> Parser (AST) -> Type Checker / Domain Inference -> Typed IR -> Target Code (GLSL / Bytecode).

### Reference Blueprints:
- **[(any)]** **(any)**: _mal - Make a Lisp_ — `https://github.com/kanaka/mal#mal---make-a-lisp`
- **[Assembly]** **Assembly**: _Jonesforth_ — `https://github.com/nornagon/jonesforth/blob/master/jonesforth.S`
- **[C]** **C**: _Baby's First Garbage Collector_ — `http://journal.stuffwithstuff.com/2013/12/08/babys-first-garbage-collector/`
- **[C]** **C**: _Build Your Own Lisp: Learn C and build your own programming language in 1000 lines of code_ — `http://www.buildyourownlisp.com/`
- **[C]** **C**: _Writing a Simple Garbage Collector in C_ — `http://maplant.com/gc.html`
- **[C]** **C**: _C interpreter that interprets itself._ — `https://github.com/lotabout/write-a-C-interpreter`
- **[C]** **C**: _A C & x86 version of the "Let's Build a Compiler" by Jack Crenshaw_ — `https://github.com/lotabout/Let-s-build-a-compiler`
- **[C]** **C**: _A journey explaining how to build a compiler from scratch_ — `https://github.com/DoctorWkt/acwj`

---

## 🏗 Domain: Regex Engine (9 Canonical Blueprints)

### Core Architectural Invariants:
- **Minimal Zero-Framework Architecture**: Explicit memory ownership, deterministic tick update, clear dataflow.

### Reference Blueprints:
- **[C]** **C**: _A Regular Expression Matcher_ — `https://www.cs.princeton.edu/courses/archive/spr09/cos333/beautiful.html`
- **[C]** **C**: _Regular Expression Matching Can Be Simple And Fast_ — `https://swtch.com/~rsc/regexp/regexp1.html`
- **[Go]** **Go**: _How to build a regex engine from scratch_ — `https://rhaeguard.github.io/posts/regex`
- **[JavaScript]** **JavaScript**: _Build a Regex Engine in Less than 40 Lines of Code_ — `https://nickdrane.com/build-your-own-regex/`
- **[JavaScript]** **JavaScript**: _How to implement regular expressions in functional javascript using derivatives_ — `http://dpk.io/dregs/toydregs`
- **[JavaScript]** **JavaScript**: _Implementing a Regular Expression Engine_ — `https://deniskyashif.com/2019/02/17/implementing-a-regular-expression-engine/`
- **[Perl]** **Perl**: _How Regexes Work_ — `https://perl.plover.com/Regex/article.html`
- **[Python]** **Python**: _Build Your Own Regular Expression Engines: Backtracking, NFA, DFA_ — `https://build-your-own.org/b2a/r0_intro`

---

## 🏗 Domain: Shell (7 Canonical Blueprints)

### Core Architectural Invariants:
- **Minimal Zero-Framework Architecture**: Explicit memory ownership, deterministic tick update, clear dataflow.

### Reference Blueprints:
- **[C]** **C**: _Tutorial - Write a Shell in C_ — `https://brennan.io/2015/01/16/write-a-shell-in-c/`
- **[C]** **C**: _Let's build a shell!_ — `https://github.com/kamalmarhubi/shell-workshop`
- **[C]** **C**: _Writing a UNIX Shell_ — `https://indradhanush.github.io/blog/writing-a-unix-shell-part-1/`
- **[C]** **C**: _Build Your Own Shell_ — `https://github.com/tokenrove/build-your-own-shell`
- **[C]** **C**: Write a shell in C — `https://danishpraka.sh/posts/write-a-shell/`
- **[Go]** **Go**: _Writing a simple shell in Go_ — `https://sj14.gitlab.io/post/2018-07-01-go-unix-shell/`
- **[Rust]** **Rust**: _Build Your Own Shell using Rust_ — `https://www.joshmcguigan.com/blog/build-your-own-shell-rust/`

---

