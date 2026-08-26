# CADENCE — คู่มือทำความเข้าใจโค้ด

**ประเภทเอกสาร:** เอกสารมีชีวิต อัปเดตเมื่อโครงสร้างเปลี่ยน
**เขียนให้ใคร:** คนที่กลับมาอ่านโปรเจกต์นี้หลังจากห่างไปนาน หรือคนที่มาจากสาย TypeScript / Go
**ภาษา:** ไทย ตามข้อยกเว้นใน `CLAUDE.md` §12 — เอกสารนี้มีไว้ให้ maintainer อ่านเข้าใจ ไม่ใช่ผลงานวิจัย
**อัปเดตล่าสุด:** 2026-08-24 ตอนจบ M1a

ไฟล์นี้ตอบว่า **มีอะไรอยู่บ้าง และมันต่อกันยังไง** ไม่ตัดสินใจอะไรทั้งสิ้น — แผนงานอยู่ที่
`docs/DIRECTION.md` กฎอยู่ที่ `CLAUDE.md` การตัดสินใจอยู่ที่ `docs/specs/` **ถ้าไฟล์นี้ขัดกับ
สามอันนั้น สามอันนั้นถูก ไฟล์นี้เก่า**

---

# 1. โปรเจกต์นี้คืออะไร ในย่อหน้าเดียว

CADENCE รันการจำลองจราจรบน SUMO แล้วแปลงแต่ละรอบการรันเป็น **โฟลเดอร์ข้อมูลที่อธิบายตัวเองได้**

ตอนนี้ **ยังไม่มีตัวควบคุมไฟจราจร และยังไม่มีการเรียนรู้ของเครื่องเลยสักบรรทัด** ไฟจราจรวิ่ง
โปรแกรมตายตัวที่ SUMO มีมาให้

สิ่งที่มีอยู่คือ **เครื่องมือวัด** — โค้ดที่เฝ้าดูการจำลองแล้วบันทึกทุกวินาทีว่าเลนไหนกำลังทำอะไร
ไฟสัญญาณเป็นอะไร ในรูปแบบที่ไม่ผูกกับ SUMO ไมล์สโตนถัดไปจะเสียบตัวควบคุมเข้ากับรูปแบบนั้น

เหตุผลที่ต้องสร้างเครื่องมือวัดก่อน: **ถ้ามันวัดผิด งานทดลองทุกชิ้นที่เคยใช้มันเป็นโมฆะหมด**

---

# 2. คำสั่งห้าอันที่ต้องรู้

```bash
make check        # ด่านหลัก: lint + format + type + doc consistency + test — รันก่อนจะบอกว่าอะไรเสร็จ
make test         # เฉพาะเทสต์
uv sync           # ติดตั้ง dependency (เทียบเท่า npm ci / go mod download)
uv run cadence run --scenario scenarios/s0_turning/v1     # สร้างโฟลเดอร์ผลลัพธ์หนึ่งรอบ
uv run cadence validate-scenario --scenario scenarios/s0_turning/v1
```

`uv run X` แปลว่า "รัน X ข้างใน virtual environment ของโปรเจกต์นี้" — Python ไม่มี
`node_modules` ในโฟลเดอร์โปรเจกต์ dependency อยู่ใน environment ที่ซ่อนไว้ และ `uv run` คือ
ตัวที่ชี้ไปหามัน คิดว่าเป็น `npx` ที่ pin เวอร์ชัน Python ให้ด้วย

---

# 3. พจนานุกรมสำหรับคนมาจาก TypeScript / Go

ทุกอย่างที่ไม่คุ้นในโปรเจกต์นี้ เทียบกับของที่คุ้น

## เครื่องมือ

| ในโปรเจกต์นี้ | คุณรู้จักในชื่อ | หมายเหตุ |
|---|---|---|
| `uv` | `npm` + `nvm` + `go mod` รวมกัน | `uv sync` ติดตั้ง, `uv run` สั่งรัน, `uv.lock` commit ไว้เหมือน `package-lock.json` |
| `pyproject.toml` | `package.json` + `tsconfig.json` + `.eslintrc` | ไฟล์เดียวเก็บทั้ง dependency **และ** config ของทุกเครื่องมือ |
| `ruff` | `eslint` + `prettier` | `ruff check` ตรวจ, `ruff format` จัดรูปแบบ เร็วมากเพราะเขียนด้วย Rust |
| `mypy --strict` | `tsc --strict` | type ของ Python เป็นตัวเลือกและหายไปตอนรัน mypy คือสิ่งเดียวที่บังคับใช้ `--strict` = ห้ามมี implicit any |
| `pytest` | `jest` / `go test` | ฟังก์ชันชื่อขึ้นต้น `test_` คือเทสต์ ไม่ต้อง import framework |
| `hypothesis` | property-based testing (`fast-check`, `gopter`) | สุ่ม input เป็นร้อยแบบมาพยายามทำให้ invariant พัง |
| `pre-commit` | `husky` | git hooks |
| `Makefile` | `npm scripts` | อันที่ต้องจำคือ `make check` |

## ไลบรารี

| ไลบรารี | ทำอะไร | เทียบได้กับ |
|---|---|---|
| `traci` / `libsumo` | สองวิธีสั่งงาน SUMO — `traci` คุยผ่าน socket กับ process แยก ส่วน `libsumo` คือ API เดียวกันที่คอมไพล์เข้ามาใน process เดียวกัน (เร็วกว่า แต่รันได้ทีละหนึ่งการจำลอง) | network client กับ embedded library ที่มีหน้าตาเหมือนกัน |
| `sumolib` | อ่านไฟล์ XML ของถนนแบบ offline โดยไม่ต้องรันการจำลอง | parser library |
| `pydantic` | สร้าง data model ที่ตรวจสอบค่าตอนรัน จาก type annotation | `zod` หรือ struct tag ของ Go + validator |
| `polars` | dataframe อ่านเขียน Parquet | pandas ที่เร็วกว่า คิดว่าเป็นตารางในหน่วยความจำที่รู้ชนิดข้อมูลของตัวเอง |
| `typer` | สร้าง CLI จาก signature และ type hint ของฟังก์ชัน | `cobra`, `commander` |
| Parquet | รูปแบบไฟล์ตารางแบบ binary เก็บเป็นคอลัมน์ | CSV ที่รู้ชนิดข้อมูลของแต่ละคอลัมน์และบีบอัดได้ดี |

## สำนวน Python ที่ใช้เยอะในโปรเจกต์นี้

| สำนวน | แปลว่า | เทียบ TS / Go |
|---|---|---|
| `@dataclass(frozen=True, slots=True)` | value object — แก้ไม่ได้ และมีได้เฉพาะฟิลด์ที่ประกาศไว้ | interface ที่เป็น `readonly` ทั้งหมด / struct ของ Go ที่ส่งด้วยค่า `slots` ทำให้เล็กและเร็วขึ้นด้วย |
| `NewType("LaneId", str)` | ชนิดข้อมูลแยกต่างหาก แต่ตอนรันยังเป็น `str` | branded type ของ TS, `type LaneId string` ของ Go |
| `StrEnum` | enum ที่สมาชิก**เป็น**สตริงจริง ๆ | string enum ของ TS |
| `Mapping[K, V]` | มุมมองแบบอ่านอย่างเดียวของ dict | `ReadonlyMap` |
| `MappingProxyType(d)` | ห่อ dict ไม่ให้ผู้เรียกแก้ได้ | `Object.freeze` |
| `X \| None` | เป็น null ได้ | `X \| null`, pointer-or-nil ของ Go |
| `with SumoConnection(...) as conn:` | ทรัพยากรที่มีขอบเขต — โค้ดเก็บกวาดทำงานตอนออกเสมอ แม้เกิด exception | `defer conn.Close()` หรือ `try/finally` |
| `if TYPE_CHECKING:` | import เฉพาะให้ type checker เห็น ไม่ import ตอนรัน | `import type` — ที่นี่ใช้แก้ import วน |
| `__post_init__` | ทำงานหลัง dataclass ถูกสร้าง | บล็อกตรวจสอบค่าใน constructor |

**ทำไมต้อง `frozen=True` ทุกที่:** state object พวกนี้จะถูกส่งให้ตัวควบคุมในไมล์สโตนถัดไป
ถ้าตัวควบคุมแก้ state ที่ได้รับมาได้ ตัวควบคุมสองตัวที่ดู step เดียวกันอาจเห็นไม่ตรงกัน
การทำให้แก้ไม่ได้เปลี่ยนเรื่องนี้จาก "ไม่ควรทำ" เป็น "ทำไม่ได้"

---

# 4. แผนที่โฟลเดอร์

```
src/cadence/                 แกนของแพลตฟอร์ม — ตัวเครื่องมือวัด
├── types.py                 ชนิด id แบบ branded: LaneId, EdgeId, MovementId, ...
├── cli.py                   `cadence run` และ `cadence validate-scenario`
└── simulation/
    ├── scenario.py          อ่าน scenarios/<id>/v<N>/ แล้วแฮชไฟล์
    ├── topology.py          ถนน "เป็น" อะไร (เลน, connection, movement, phase)
    ├── state.py             ถนน "กำลังทำ" อะไรอยู่ตอนนี้ (canonical state)
    ├── events.py            departed / arrived / teleport / collision และ StepResult
    ├── ground_truth.py      ตารางไขว้ทิศทางเลี้ยว — ข้อมูลชั้นความลับ (ดู §6)
    ├── artifacts.py         เขียนโฟลเดอร์ผลลัพธ์ (Parquet)
    ├── manifest.py          บันทึกที่มาที่ไปของรอบการรัน
    └── sumo/                ← แพ็กเกจเดียวที่แตะ SUMO ได้
        ├── binding.py       โหลด traci หรือ libsumo
        ├── command.py       ประกอบ argument ที่จะส่งให้ SUMO
        ├── connection.py    วงจรชีวิต: start, step, read, close
        ├── signals.py       ถอดรหัสตัวอักษรไฟสัญญาณของ SUMO เป็น SignalState
        ├── topology_reader.py   อ่านถนนหนึ่งครั้ง ตอนเริ่ม
        ├── extract.py       ดึงข้อมูลรายวินาที + ตรวจจับการข้ามแยก + ground truth
        └── validation.py    ตรวจถนนของ scenario ก่อนรัน

scenarios/<id>/v<N>/         นิยาม scenario ที่แก้ไม่ได้ (ถนน + ความต้องการเดินทาง + config)
tools/                       สคริปต์ที่ไม่ใช่ส่วนหนึ่งของแพลตฟอร์ม
tests/                       โครงสร้างสะท้อน src/
docs/, research/             การตัดสินใจและเหตุผลเบื้องหลัง
studies/                     การทดลอง (ยังไม่มี จะมาตอน M6)
```

**กฎโครงสร้างข้อเดียวที่ต้องรู้:** ห้ามโค้ดนอก `src/cadence/simulation/sumo/` import `traci`,
`libsumo` หรือ `sumolib` **มีเทสต์บังคับอยู่จริง** นั่นคือสิ่งที่ทำให้โค้ดที่เหลือไม่ผูกกับ
ตัวจำลอง แทนที่จะแค่ตั้งใจว่าจะไม่ผูก

---

# 5. หนึ่งรอบการรัน ทำงานยังไงจริง ๆ

นี่คือทั้งระบบในภาพเดียว ตามมันหนึ่งรอบแล้วโค้ดที่เหลือจะอ่านง่ายขึ้นมาก

```
uv run cadence run --scenario scenarios/s0_turning/v1
│
└── cli.run_scenario()
    │
    ├── load_scenario(root)                      scenario.py
    │     อ่าน scenario.yaml, หาไฟล์ถนนกับ demand, แฮชไว้
    │
    ├── run_dir.mkdir(exist_ok=False)            ตั้งชื่อจาก เวลา + scenario + seed
    │
    ├── with SumoConnection(...) as connection:  connection.py — เส้นแบ่งกับ SUMO
    │   │
    │   │   ตอนเข้า:
    │   │     load_binding(traci | libsumo)      binding.py
    │   │     build_sumo_command(...)            command.py — ตรึงทุก flag เพื่อความ deterministic
    │   │     binding.start(argv)                SUMO เริ่มทำงานแล้ว
    │   │     read_topology(binding)             topology_reader.py — ครั้งเดียว ไม่ใช่ทุก step
    │   │       → NetworkTopology { lanes, connections, movements, phases }
    │   │     สร้าง StateExtractor, TraversalDetector, GroundTruthReader
    │   │
    │   ├── วนจนกว่า connection.is_finished():
    │   │     │
    │   │     ├── result = connection.step()     → StepResult
    │   │     │     binding.simulationStep()     เดินการจำลองไปหนึ่งวินาที
    │   │     │     events      ← ออกตัว / ถึงที่หมาย / teleport / ชน
    │   │     │     teleports   ← เลนที่รถแต่ละคันจากไป ตอนถูก teleport
    │   │     │     traversals  ← TraversalDetector.observe(): ใครข้ามแยกไปแล้วบ้าง
    │   │     │     state       ← StateExtractor.extract(): ภาพนิ่ง canonical ของวินาทีนี้
    │   │     │
    │   │     ├── log.append(result.events)
    │   │     └── recorder.record(state, teleports, connection.read_ground_truth())
    │   │                                        ↑ ทางเดียวที่เข้าถึงข้อมูลชั้นความลับ เรียกด้วยชื่อ
    │   │
    │   └── terminal_time_s, termination_reason  (drained | horizon | aborted)
    │
    ├── build_manifest(...)                      manifest.py — ที่มาที่ไป
    ├── log.to_parquet(events.parquet)
    ├── recorder.write()                         artifacts.py — แถวที่พักไว้ทั้งหมด → Parquet
    ├── recorder.write_tripinfo(tripinfo.xml)    XML รายเที่ยวของ SUMO → Parquet
    └── เขียน manifest.json                       เป็นอันสุดท้าย การมีอยู่ของมันแปลว่ารันจบจริง
```

**สองรายละเอียดที่ควรจำ**

*topology อ่านครั้งเดียว แต่ state อ่านทุก step* — รูปร่างถนนไม่เปลี่ยนระหว่างรัน อ่านทุก step
คือเสียแรงเปล่า และเปิดช่องให้สองอย่างเพี้ยนจากกัน

*recorder พักข้อมูลไว้ในหน่วยความจำแล้วเขียนทีเดียวตอนจบ* — หนึ่งรอบการรันมีขนาดไม่กี่ร้อย
กิโลไบต์ การทยอยเขียนลงดิสก์จึงไม่ได้อะไรเลย แต่แลกมาด้วยความเสี่ยงที่จะได้ไฟล์ครึ่ง ๆ กลาง ๆ

## หน้าตาโฟลเดอร์ผลลัพธ์

```
20260824T193045__s0_turning-v1__none-v1__seed1/
├── manifest.json                  ที่มา: commit, seed, เวอร์ชัน, รันจบเพราะอะไร
├── events.parquet                 ออกตัว / ถึงที่หมาย / teleport / ชน
├── topology/                      รูปร่างถนน — เพื่อให้โฟลเดอร์นี้ไม่ต้องพึ่งไฟล์อื่นเลย
│   ├── lane.parquet               lane_id, edge_id, lane_index, length_m, max_speed_mps
│   ├── connection.parquet         from_lane → to_lane, ทิศทางเลี้ยว, อยู่ movement ไหน
│   └── tls_program.parquet        ทุก phase × ทุก connection ที่ควบคุม พร้อมสัญญาณ
├── state/                         สิ่งที่ตัวควบคุมมีสิทธิ์เห็น
│   ├── lane.parquet               รายวินาที: จำนวนรถ, จำนวนที่หยุด, ความเร็วเฉลี่ย, ความหนาแน่น, เวลารอ
│   ├── intersection.parquet       รายวินาที: อยู่ phase ไหน มานานเท่าไร
│   ├── signal.parquet             รายวินาที: สัญญาณของทุก connection
│   ├── movement.parquet           รายวินาที: สัญญาณของทุก movement
│   ├── network.parquet            รายวินาที: รถในระบบ / รอออกตัว / ออกแล้ว / ถึงแล้ว / teleport
│   ├── traversal.parquet          รถแต่ละคันที่ข้ามแยก และข้ามด้วย movement ไหน
│   └── teleport.parquet           การ teleport แต่ละครั้ง และเลนที่จากไป
├── ground_truth/                  สิ่งที่ตัวควบคุม **ห้าม** เห็น
│   └── lane_turn.parquet          รายวินาที รายเลน: มีรถกี่คันตั้งใจไปยัง edge ถัดไปอันไหน
└── evaluation/                    ข้อมูลรายเที่ยว หลังจบ — ไม่ใช่ทั้งสองอย่างข้างบน
    └── tripinfo.parquet           บันทึกของ SUMO เอง: ระยะเวลา, เวลารอ, เวลาที่เสียไป
```

---

# 6. สองโลกของข้อมูล และเหตุผลที่โฟลเดอร์ถูกแบ่ง

**นี่คือแนวคิดที่สำคัญที่สุดในโปรเจกต์นี้**

**ข้อมูลที่สังเกตได้จริง** คือสิ่งที่แยกจริงบนถนนรู้ได้จากเซนเซอร์จริง — เลนนี้มีรถกี่คัน หยุดกี่คัน
ไฟเป็นสีอะไร ตัวควบคุมใช้ได้ทั้งหมด

**ข้อมูลชั้นความลับ (ground truth)** คือสิ่งที่มีแต่ตัวจำลองเท่านั้นที่รู้ ตัวอย่างสำคัญคือ:
บนเลนที่ใช้ร่วมกัน **ในรถที่ต่อคิวอยู่ มีกี่คันที่ตั้งใจจะเลี้ยวซ้าย**

ไม่มีเซนเซอร์ไหนในโลกตอบคำถามนี้ได้ ที่เราบันทึกไว้เพราะจำเป็นต้องใช้**ตรวจสอบ**ว่าตัวประมาณค่า
ทำงานถูกไหม ใช้ดีบั๊ก และใช้ทำการทดลองแบบ "oracle" ที่ติดป้ายชัดเจนว่าโกง — **แต่ตัวควบคุมที่
อ่านมันคือการโกง และผลลัพธ์จะไม่มีความหมายใด ๆ**

มีสามกลไกกันไว้ และตั้งใจให้ทับซ้อนกัน:

1. **ห้าม import** — ไม่มีโมดูลนอก `simulation/` ที่ import `ground_truth` ได้
2. **บัญชีรายชื่อแบบตรงเป๊ะ** — เอาเซตของไฟล์ที่*เอ่ยถึง*คำว่า `ground_truth` มาเทียบว่าเท่ากับ
   รายชื่อที่เขียนไว้พอดี การขยายพื้นที่ชั้นความลับต้องเป็นการแก้โดยเจตนา และเทียบทั้งสองทาง
3. **เมธอดที่ต้องเรียกด้วยชื่อ** — `connection.read_ground_truth()` **จงใจไม่ให้**คืนมาพร้อม
   `step()` เหมือนของอย่างอื่น การเอื้อมไปหยิบข้อมูลชั้นความลับจึงเห็นชัดตอน review และ grep เจอ

**ข้อจำกัดที่รู้อยู่ บันทึกเป็น `ST-D23`:** สามข้อนั้นกั้น**โค้ด** แต่ไม่มีอะไรกั้น**การอ่านไฟล์**
`state/traversal.parquet` บวกกับ `evaluation/tripinfo.parquet` ประกอบตารางชั้นความลับกลับมาได้
ราว 89% เรื่องนี้จะตัดสินกันที่ M1b

---

# 7. ไล่ทีละโมดูล

อ่านคู่กับ §5 — แต่ละหัวข้อบอกว่าโมดูลนั้นรับผิดชอบอะไร และส่งอะไรต่อ

### `types.py`
ชนิด id แบบ branded ใน SUMO `"e1"` คือ edge และ `"e1_0"` คือ lane ทั้งคู่เป็นสตริงธรรมดา
ส่งผิดที่กันเมื่อไรคือบั๊กเงียบ `NewType` ทำให้ type checker จับได้ ไม่มีต้นทุนตอนรันเลย

### `simulation/scenario.py`
อ่าน `scenarios/<id>/v<N>/scenario.yaml` เป็น `ScenarioConfig` ที่ตรวจค่าแล้ว หาไฟล์ถนนกับ
demand แล้วแฮชทุกอย่าง แฮชไปอยู่ใน manifest เพื่อให้พิสูจน์ได้ว่ารอบนั้นใช้ scenario ไบต์ไหน

### `simulation/sumo/binding.py`
โมดูลเดียวที่ `import traci` / `import libsumo` ได้ คืนตัวโมดูลที่ขอมาเป็นค่ากลับ
**ทุกอย่างที่อยู่ถัดจากนี้รับโมดูลนั้นมาเป็น argument แทนที่จะ import เอง** ซึ่งเป็นเหตุผลที่
แพ็กเกจนี้เทสต์ด้วยของปลอมได้

### `simulation/sumo/command.py`
ประกอบ argument ที่ส่งให้ SUMO ทุก flag ที่มีผลต่อความ deterministic ถูกตรึงไว้ชัดเจน
แทนที่จะปล่อยตาม default ของ SUMO — เพื่อให้การอัปเกรด SUMO เปลี่ยนผลลัพธ์เงียบ ๆ ไม่ได้

### `simulation/sumo/signals.py`
ถอดรหัส "lamp string" ของไฟจราจร SUMO แทนสัญญาณทั้งแยกด้วยสตริงเดียวแบบ `"GGrrGGrr"`
หนึ่งตัวอักษรต่อหนึ่ง connection ที่ควบคุม โมดูลนี้คือ**ที่เดียว**ที่เข้าใจตัวอักษรพวกนั้น
ที่อื่นใช้ enum `SignalState` ทั้งหมด เจอตัวอักษรที่ไม่รู้จักจะ**โยน error ไม่ใส่ค่า default** —
สัญญาณไฟที่ถูก default เงียบ ๆ คือการรับประกันความปลอดภัยที่ไม่มีใครเคยให้ไว้

### `simulation/topology.py` + `sumo/topology_reader.py`
**รูปร่าง**ของถนน: มีเลนอะไรบ้าง มี connection ไหนข้ามแยกบ้าง connection พวกนั้นรวมกลุ่มเป็น
movement อะไร และโปรแกรมไฟมี phase อะไรบ้าง

**movement** คือ "รถที่ไปจากขาเข้านี้ ออกทางนั้น" เช่น เลี้ยวซ้ายจากขาเหนือ มันถูกระบุด้วยคู่
`(edge ขาเข้า, edge ขาออก)` ซึ่งไม่ใช่ความชอบส่วนตัว: `netconvert --tls.group-signals` ของ
SUMO เองก็จัดกลุ่มสัญญาณด้วยคู่นี้เป๊ะ ๆ คีย์นี้จึงตรงกับสิ่งที่ตัวจำลองเองถือว่าเป็น movement เดียวกัน

### `simulation/state.py`
ภาพนิ่ง canonical ทั้งหมดเป็น frozen dataclass:

- `LaneState` — จำนวนรถ, ความเร็วเฉลี่ย, ความหนาแน่น, เวลารอ **ปฏิเสธค่าที่เป็นไปไม่ได้ทาง
  กายภาพตั้งแต่ตอนสร้าง** (รถที่หยุดมากกว่ารถทั้งหมด, ความหนาแน่นเกิน 0–1)
- `SignalState` — สัญญาณที่ถอดรหัสแล้ว มี property `permits_movement` ที่เอามาจากการจัดหมวด
  ของ SUMO เอง เพื่อไม่ให้ adapter สองตัวเห็นไม่ตรงกันว่าอะไรคือ "ไปได้"
- `MovementState`, `IntersectionState`, `NetworkState`, `Traversal`, `TeleportEvent`
- `CanonicalTrafficState` — ทุกอย่างข้างบนของหนึ่งวินาที **บวก topology แบบอ้างอิง** ถ้าไม่มี
  topology ชั้น movement จะเป็นแค่ของประดับ: การเอ่ยชื่อ movement กับเอ่ยชื่อ lane ไว้ใน
  object เดียวกันไม่ได้เชื่อมอะไรเข้าด้วยกันเลย

### `simulation/sumo/extract.py`
สามส่วนทำงานร่วมกัน:

- **`StateExtractor`** — ถาม SUMO หนึ่งครั้งต่อหนึ่งปริมาณต่อหนึ่ง step แล้วประกอบเป็น
  `CanonicalTrafficState`
- **`TraversalDetector`** — จำว่ารถแต่ละคันอยู่เลนไหน แล้วสังเกตว่ามันข้ามแยกไปถึง edge ใหม่
  เมื่อไร ระบุด้วย edge ขาออก ซึ่ง**เลือกจากการวัด** ไม่ใช่จากการเถียง: บน fixture ทดสอบ
  การใช้ via lane เป็นคีย์ได้ 322 ครั้ง ใช้คู่เลนได้ 306 ใช้ edge ขาออกได้ 315 — พอดีหนึ่งคันต่อหนึ่งครั้ง
- **`GroundTruthReader`** — ตารางไขว้ชั้นความลับ ว่าแต่ละเลนมีรถกี่คันที่ตั้งใจไป edge ถัดไปอันไหน
  อ่านจากเส้นทางของรถ

### `simulation/artifacts.py`
`RunRecorder` พักแถวข้อมูลไว้ทีละ step แล้วเขียนทั้งโฟลเดอร์ทีเดียว **ทุกตารางประกาศ schema
ของตัวเอง** เพราะถ้าไม่ประกาศ ตารางว่างจะกลายเป็นไฟล์ที่ไม่มีคอลัมน์เลย — รอบการรันที่**เงียบที่สุด**
จะกลายเป็นรอบเดียวที่อ่านไม่ได้

### `simulation/manifest.py`
ทุกอย่างที่ต้องใช้ทำซ้ำรอบการรัน: commit sha, แฮชของ working tree ที่ยังไม่ commit ถ้ามี,
เวอร์ชัน SUMO และ Python, แพลตฟอร์ม, seed, แฮชของ scenario และรันจบด้วยเหตุอะไร
`cadence_dirty` คำนวณ**มาจาก** digest แทนที่จะคำนวณแยก สองอย่างนี้จึงขัดกันเองไม่ได้

### `cli.py`
ต่อทุกอย่างเข้าด้วยกัน และเตือนทาง stderr เมื่อรอบการรันมาจาก working tree ที่ยังไม่ commit
เพราะคำเตือนแบบนี้มีประโยชน์ก็ต่อเมื่อไปถึงคนที่กำลังรัน ในจังหวะที่เขายังทำอะไรกับมันได้

---

# 8. เทสต์ และแต่ละแบบมีไว้ทำอะไร

`make check` รันเทสต์ 230 ตัว ซึ่งไม่ได้เป็นชนิดเดียวกันทั้งหมด

| ชนิด | ตอบคำถามว่า | ตัวอย่างในโปรเจกต์นี้ |
|---|---|---|
| **Unit** | ฟังก์ชันนี้คำนวณถูกไหม | ถอดรหัสไฟสัญญาณ, จัดกลุ่ม movement |
| **Property** (`hypothesis`) | invariant นี้จริงกับ input **ทุกแบบ** ไหม | ความหนาแน่นอยู่ใน 0–1, รถที่หยุดไม่เกินรถทั้งหมด |
| **Architecture** | กฎเชิงโครงสร้างยังอยู่ไหม | ไม่มีอะไรนอก `sumo/` import traci, บัญชีชั้นความลับตรงเป๊ะ |
| **Integration** (`@pytest.mark.sumo`) | ทำงานกับการจำลองจริงได้ไหม | 315 traversal, 16 จาก 16 connection มีรถวิ่ง |
| **Reproducibility** | input เดิม ได้ไบต์เดิมไหม | libsumo กับ traci เขียน Parquet ตรงกันทุกไบต์ |

`@pytest.mark.sumo` ติดไว้บนเทสต์ที่เปิด process SUMO จริง ซึ่งช้ากว่า ข้ามได้ด้วย
`uv run pytest -m "not sumo"`

**กฎเบื้องหลังตัวเลขทุกตัว:** ตัวเลขทุกตัวที่ assert ในเทสต์มาจากการ**วัดจริง**โดยรัน fixture
ไม่เคยมาจากการเดา **เมื่อตัวเลขที่วัดได้ขัดกับโค้ด แปลว่าโค้ดผิด — ไม่ใช่แก้ตัวเลขให้ตรงกับโค้ด**
กฎนี้คือเหตุผลที่จับความผิดพลาดเรื่องคีย์ของ traversal ได้ก่อนจะมีอะไรสร้างทับมัน

---

# 9. ตอนนี้อยู่ตรงไหน

```
M0  Simulation Harness        เสร็จ  วงจรชีวิต SUMO แบบ deterministic, โหลด scenario, seed, event
M1a Canonical State           เสร็จ  ← ทุกอย่างในเอกสารนี้
M1b Metrics                   ถัดไป  ทะเบียน metric, การแบ่งคิว, ประมาณสัดส่วนการเลี้ยว
M2  Signal Safety + Contract         อินเทอร์เฟซตัวควบคุม — ตัวควบคุมตัวแรกเกิดได้ตรงนี้
M3  Validation Controllers           fixed-time และ actuated ของ SUMO — บททดสอบว่า M2 ใช้ได้จริง
M4  RL Adapter                       Gymnasium adapter, observation, reward
M5  PPO (+ DQN)
M6  Single-Intersection Experiments
M7  Real-World Intersection          ไมล์สโตนที่ใช้แสดงผลงาน
M8  Corridor + Max-Pressure
M9  Network-Aware RL vs Max-Pressure ข้อสรุปของ Study 1
```

**ยังไม่มีตัวควบคุมใด ๆ** ไฟจราจรวิ่งโปรแกรมตายตัวของ SUMO ใน manifest จึงบันทึกว่า
`controller_id = "none"` ด้วยเหตุผลนี้พอดี

## สิ่งที่ M1a จงใจทิ้งไว้ไม่ทำ

สองเรื่อง ทั้งคู่บันทึกเป็นการตัดสินใจไว้แล้ว และทั้งคู่เป็น**เงื่อนไขก่อนหน้า**ของงานชิ้นแรกใน M1b
ไม่ใช่ของที่ทำก็ดีไม่ทำก็ได้:

- **`ST-D22`** — การแบ่งสัดส่วนการเลี้ยว**รายเลน**ในตารางชั้นความลับ **ยังไม่มีอะไรตรวจสอบมันได้**
  ถ้าสลับป้าย edge ถัดไประหว่างสอง movement ที่เลนหนึ่งรองรับ เนื้อในตารางจะเปลี่ยนไป 74%
  **และจะไม่มีเทสต์ตัวไหนล้มเลยสักตัว** เพราะตารางไม่มีคีย์ระบุตัวรถ จึงกระทบยอดกับ
  traversal stream ไม่ได้ ตัวประมาณสัดส่วนการเลี้ยวของ M1b คือสิ่งแรกที่จะเอามาเทียบกับตารางนี้
  มันจึงต้องถูกตรวจสอบก่อนที่จะเชื่อถือได้
- **`ST-D23`** — การแบ่งชั้นความลับกั้นโค้ด ไม่ได้กั้นข้อมูล (ดู §6)

รายการเต็มของสิ่งที่ M1a ส่งต่อ อยู่ที่ §12 ของ `docs/specs/2026-08-23-m1a-canonical-state.md`

---

# 10. อยากรู้อะไรต่อ ดูที่ไหน

| อยากรู้ | อ่าน |
|---|---|
| แผนงานและคำถามที่ยังไม่ตัดสิน | `docs/DIRECTION.md` |
| กฎที่โค้ดต้องทำตาม | `CLAUDE.md` |
| ทำไมออกแบบมาแบบนี้ | `docs/specs/` — บันทึกการตัดสินใจ ลงวันที่ แก้ไม่ได้ |
| `XX-Dnn` หมายถึงอะไร | `research/decisions.yaml` |
| ทำไมโปรเจกต์นี้ถึงมีอยู่ | `docs/ORIGIN.md` |
| จุดบกพร่องที่รู้แล้วในคลังงานวิจัย | `research/INDEX.md` §6 |

## ฉบับอ่านง่าย

`docs/guide/` เก็บคู่มือฉบับหน้าเว็บไว้สองใบ เปิดด้วยเบราว์เซอร์ได้เลย

| ไฟล์ | อ่านกี่นาที | ตอบคำถามว่า |
|---|---|---|
| `2026-08-25-m1a-orientation.html` | 3 | ระบบนี้คืออะไร หนึ่งรอบการรันไหลยังไง |
| `2026-08-25-m1a-simulation-internals.html` | 10 | `simulation/` ทำงานยังไงจริง ๆ ทีละกลไก |

ทั้งสองใบเป็น **ภาพนิ่งลงวันที่** แบบเดียวกับ `docs/specs/` — บันทึกว่าตอนจบ M1a ระบบเป็นแบบนี้
**มันจะไม่ถูกอัปเดตตามโค้ด** ไฟล์นี้ต่างหากที่ตามโค้ด ถ้าสองอันขัดกัน ไฟล์นี้ถูก และภาพนิ่งนั้น
บอกว่าโค้ดเปลี่ยนไปตั้งแต่เมื่อไร ซึ่งก็เป็นข้อมูลเหมือนกัน

ฟอนต์โหลดจาก Google Fonts เปิดแบบออฟไลน์ยังอ่านได้ แค่ตัวอักษรเปลี่ยนไปใช้ของเครื่อง
