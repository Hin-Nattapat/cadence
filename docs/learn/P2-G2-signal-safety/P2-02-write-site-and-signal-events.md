# P2-02 จุดเขียนไฟจุดเดียว และตาราง signal event

> Phase P2 (M2 Signal Safety + Controller Contract) · Gate G2 · Ticket P2-02 · Issue #15 · Slice: ไม่มี · Decisions: `SIG-D04`, `SIG-D08`

## ทำไม

ตอนนี้ executor (`control/executor.py`) ตัดสินใจได้แล้วว่าจะเปลี่ยนไฟเมื่อไหร่ แต่ตัดสินใจอยู่ในอากาศ
มันคืนค่าออกมาเป็น **คำสั่งที่เป็นข้อมูล** สองแบบ คือ `SetPhase` (ไปที่ phase นี้) กับ
`SetRemainingDuration_s` (ยืด phase นี้ออกไปอีกเท่านี้) ยังไม่มีโค้ดตัวไหนส่งคำสั่งพวกนี้เข้า SUMO
และสิ่งที่ executor ตัดสินใจ (`SignalEvent`) ก็ยังไม่ถูกบันทึกลงโฟลเดอร์ผลลัพธ์

ticket นี้ทำสองอย่างที่ P2-03 ต้องมีก่อนจะขับไฟบนการรันจริงได้:

1. **ท่อออกไป SUMO**: โมดูลเดียวที่แปลงคำสั่งเป็นการเรียก `trafficlight.setPhase` /
   `setPhaseDuration` ของ SUMO
2. **ที่เก็บหลักฐาน**: ตาราง `state/signal_event.parquet` หนึ่งแถวต่อการตัดสินใจของ executor

ตัวอย่างจากข้อมูลจริง: ใน `s0_turning` แยก `A0` มี stage 0 และ 2 คั่นด้วยไฟเหลือง phase 1 และ 3
(phase ละ 3 วินาที) และ min green คือ 10 วินาที ถ้ามีคนขอ stage 2 ตอนวินาทีที่ 20 executor จะคืน
`SetPhase(A0, 1)` (เข้าไฟเหลือง) และ event สองแถว ส่วนอีก 3 วินาทีต่อมาจะคืน `SetPhase(A0, 2)`
กับ `SetRemainingDuration_s` และ event อีกหนึ่งแถว ตารางที่ได้จะหน้าตาประมาณนี้:

| time_s | intersection_id | kind | from_phase_id | to_phase_id | reason |
|---|---|---|---|---|---|
| 20.0 | A0 | stage_requested | 0 | 2 | |
| 20.0 | A0 | transition_started | 0 | 2 | |
| 23.0 | A0 | stage_entered | 1 | 2 | |

ticket นี้ยังไม่ทำให้ตัวอย่างนี้เกิดขึ้นบนการรันจริง (นั่นคือ P2-03) แค่สร้างท่อกับตารางไว้ให้พร้อม
และทดสอบแต่ละชิ้นแยกกัน

## ไฟจราจรใน SUMO นับกันยังไง

### สตริงไฟ: หนึ่งตัวอักษรต่อหนึ่งการเชื่อมต่อ

แยก `A0` ใน `s0_turning` มี 16 **การเชื่อมต่อ** (connection) คือเส้นทางจากเลนขาเข้าเลนหนึ่งไปยังเลนขาออก
เลนหนึ่ง ถนนเข้าแยกมี 4 ทิศ ทิศละ 4 เส้น: เลี้ยวขวา, ตรงสองเลน, เลี้ยวซ้าย แต่ละเส้นมีเลขประจำตัว
ที่เรียกว่า **link index** (0–15) ซึ่งก็คือตำแหน่งในสตริงไฟ:

| link index | มาจากทิศ |
|---|---|
| 0–3 | บน (เหนือ) |
| 4–7 | ขวา (ตะวันออก) |
| 8–11 | ล่าง (ใต้) |
| 12–15 | ซ้าย (ตะวันตก) |

ในแต่ละทิศ ลำดับคือ ขวา, ตรง, ตรง, ซ้าย

สตริงไฟหนึ่งเส้นจึงยาว 16 ตัวอักษร ตัวที่ *i* คือสีไฟของการเชื่อมต่อ *i* ตัวอักษรที่ใช้มีความหมายดังนี้:

| ตัวอักษร | ความหมาย |
|---|---|
| `G` | เขียว มีสิทธิ์ผ่านก่อน (protected) ไม่ต้องหลบใคร |
| `g` | เขียว แต่ต้องหลบรถที่มีสิทธิ์ก่อน (permissive) เช่น เลี้ยวซ้ายตัดหน้ารถสวน |
| `y` | เหลือง |
| `r` | แดง |
| `u` | แดงพร้อมเหลือง (บางประเทศใช้ก่อนเขียว) |
| `s`, `o`, `O` | สีพิเศษที่ s0 ไม่ใช้ |

ตัวอักษรพวกนี้มีได้ที่เดียวในโค้ด คือ `simulation/sumo/signals.py` ซึ่งแปลงเป็น `SignalState` ทันที
(`ST-D04`) โค้ดส่วนอื่นไม่เคยถือสตริงไฟดิบ

### Program และ phase

**program** คือรอบไฟที่ SUMO วนเล่นเอง เป็นรายการ **phase** เรียงกัน phase หนึ่งมีสตริงไฟหนึ่งเส้น
กับระยะเวลาหนึ่งค่า เลขของ phase คือลำดับในรายการ (**phase index**) เริ่มจาก 0 program ของ `A0`
มีสี่ phase:

| phase index | ระยะเวลา | สตริงไฟ | แปลว่า | เป็น |
|---|---|---|---|---|
| 0 | 42 s | `GGGgrrrrGGGgrrrr` | เหนือ–ใต้ไปได้ (ซ้ายต้องหลบ), ตะวันออก–ตะวันตกแดง | **stage** |
| 1 | 3 s | `yyyyrrrryyyyrrrr` | เหนือ–ใต้เหลือง | transition |
| 2 | 42 s | `rrrrGGGgrrrrGGGg` | ตะวันออก–ตะวันตกไปได้, เหนือ–ใต้แดง | **stage** |
| 3 | 3 s | `rrrryyyyrrrryyyy` | ตะวันออก–ตะวันตกเหลือง | transition |

ถ้าไม่มีใครยุ่ง SUMO จะเล่น 0 → 1 → 2 → 3 → 0 … ไปเรื่อย ๆ รอบละ 90 วินาที นั่นคือการรันแบบ
`controller_id = "none"`

- **stage** (`SIG-D03`) คือ phase ที่มีเขียวอย่างน้อยหนึ่งดวงและไม่มีเหลืองเลย คือ phase ที่ให้รถวิ่ง
  ตัวควบคุมขอได้เฉพาะ stage และใช้ phase index เป็นชื่อ (`PhaseId`) ดังนั้นใน s0 ขอได้แค่ `0` กับ `2`
- **transition phase** คือ phase คั่นระหว่าง stage (ไฟเหลือง) ไม่มีใครขอได้ ต้องเล่นครบตามเวลาใน
  program เสมอ ถ้าอยากไป stage 2 จาก stage 0 ต้องผ่าน phase 1 ก่อน ลัดไม่ได้
- **min green / max green** มาจาก `signal_plan.yaml` (ใน s0 คือ 10 s และ 60 s ต่อ stage)
  stage ที่เพิ่งเริ่มต้องเขียวอย่างน้อย 10 s ก่อนจะยอมเปลี่ยน และห้ามเขียวเกิน 60 s

### คำสั่งสองแบบที่ executor คืนออกมา

executor ไม่สร้างสตริงไฟเอง (`SIG-D01`) มันเปลี่ยนไฟด้วยการ **เลือก phase index** ใน program เดิม
คำสั่งจึงมีแค่สองแบบ:

- **`SetPhase(intersection_id, phase_index)`**: "ให้แยกนี้กระโดดไปที่ phase นี้เดี๋ยวนี้"
  `signal_writer` แปลงเป็น `trafficlight.setPhase(tls_id, index)` ใช้ทั้งตอนเข้าไฟเหลือง
  (`SetPhase(A0, 1)`) และตอนเข้า stage ใหม่ (`SetPhase(A0, 2)`)
- **`SetRemainingDuration_s(intersection_id, remaining_s)`**: "phase ที่อยู่ตอนนี้ เหลือเวลาอีก
  `remaining_s` วินาที" แปลงเป็น `trafficlight.setPhaseDuration(tls_id, remaining_s)`

ทำไมต้องมีแบบที่สอง: ถ้าปล่อยไว้ SUMO จะเปลี่ยน stage เองตอนครบ 42 s ตาม program แต่คนตัดสินใจตอนนี้
ต้องเป็น executor เท่านั้น ทุกครั้งที่เข้า stage executor จึงสั่ง `SetRemainingDuration_s(A0, 60 + 1)`
คือ max green บวกอีกหนึ่ง step ทำให้นาฬิกาของ SUMO ไม่มีทางหมดก่อนที่ executor จะตัดสินใจเอง
ส่วนไฟเหลืองไม่ต้องยืด ใช้เวลา 3 s ตาม program

ใน tick เดียวกันลำดับสำคัญ: `SetPhase(A0, 2)` ต้องมาก่อน `SetRemainingDuration_s(A0, 61)`
ถ้าสลับกัน ตัวที่ถูกยืดเวลาจะเป็นไฟเหลือง phase 1 ไม่ใช่ stage 2

### `kind` ทั้งเจ็ดแบบใน `signal_event`

`from_phase_id` และ `to_phase_id` เป็น phase index ทั้งคู่ ตัวอย่างในตารางนี้อยู่บน `A0` โดยสมมติว่าตอนนี้อยู่ที่ stage 0:

| kind | เกิดเมื่อ | ตัวอย่างบน `A0` | from → to | reason |
|---|---|---|---|---|
| `stage_requested` | มีคำขอ stage อื่น และพ้น min green แล้ว | t=20 ขอ 2 | 0 → 2 | |
| `request_deferred` | คำขอถูกต้องแต่ยังทำไม่ได้ จึงเก็บไว้ทำทีหลัง | t=5 ขอ 2 (ยังไม่ครบ 10 s) | 0 → 2 | `min_green` |
| | | ขอ 0 ระหว่างไฟเหลืองที่กำลังไป 2 | 2 → 0 | `in_transition` |
| `request_superseded` | มีคำขอค้างอยู่ แล้วมีคำขอใหม่ไปอีก stage มาแทน | เกิดไม่ได้บน s0 เพราะต้องมีอย่างน้อยสาม stage | เก่า → ใหม่ | |
| `transition_started` | เริ่มเปลี่ยนจริง (สั่ง `SetPhase` เข้าไฟเหลือง) | t=20 | 0 → 2 | |
| `stage_entered` | ไฟเหลืองครบเวลาแล้ว เข้า stage ใหม่ | t=23 | 1 → 2 (from คือไฟเหลืองที่เพิ่งออก) | |
| `max_green_forced` | เขียวครบ 60 s และไม่มีคำขอค้าง จึงถูกบังคับไป stage ถัดไปตามลำดับ program | stage 0 ยืนถึง 60 s | 0 → 2 | |
| `action_rejected` | คำขอที่ผิดกฎ ถูกเปลี่ยนเป็น "ไม่ทำอะไร" แล้วจดไว้ | ขอ 1 (ไฟเหลือง) | 0 → 1 | `not_a_stage` |
| | | ขอ 0 ขณะอยู่ 0 | 0 → 0 | `already_current` |

การเปลี่ยน stage หนึ่งครั้งจะมีแถวเปิดหนึ่งแถว คือ `transition_started` หรือ `max_green_forced`
อย่างใดอย่างหนึ่ง และแถวปิดหนึ่งแถว คือ `stage_entered` เสมอ

## ทำงานยังไง

- **`simulation/sumo/signal_writer.py`** มีฟังก์ชัน `apply_signal_commands` รับคำสั่งเป็นลำดับ แล้วเรียก
  SUMO ตามลำดับเดิมเป๊ะ ภายใน tick เดียว `SetPhase` มาก่อน `SetRemainingDuration_s` เสมอ
  เพราะถ้ายืดเวลาก่อนแล้วค่อยเปลี่ยน phase ตัวที่ถูกยืดคือ phase เก่า
- **architecture test** เช็กว่าในโค้ดใต้ `src/` คำว่า `trafficlight.set` มีอยู่ในไฟล์เดียว คือไฟล์นี้
  ถ้าวันหนึ่งมีโค้ดอื่นแอบเปลี่ยนไฟเอง test จะแดงทันที
- **`RunRecorder`** ได้ตารางใหม่ `state/signal_event` ที่ประกาศ schema ไว้ล่วงหน้า การรันแบบ
  `controller_id = "none"` ไม่มี executor ก็จะได้ตารางว่างที่ยังอ่านได้และมีคอลัมน์ครบ
- **`_SCHEMAS` เปลี่ยนเป็น `SCHEMAS`** (public) เพราะ test สี่ไฟล์ import ชื่อ private นี้อยู่แล้ว
  ตกลงกันไว้ตั้งแต่ M2 spec ว่าจะเปลี่ยนตอนที่ `artifacts.py` ถูกแก้ครั้งถัดไป ซึ่งก็คือครั้งนี้
- **แก้ `by_index` ใน `artifacts.py`**: SUMO ยอมให้ link index หนึ่งตัว (ตำแหน่งหนึ่งในสตริงไฟ)
  คุมการเชื่อมต่อได้มากกว่าหนึ่งเส้น `plan.py` เก็บไว้ครบทุกเส้น แต่ `artifacts.py` ใช้ dict ธรรมดา
  จึงเก็บแค่เส้นสุดท้าย ใน `s0_turning` แต่ละ index มีเส้นเดียว บั๊กนี้เลยยังไม่โผล่ แต่แยกจริงในอนาคต
  (P7) จะเจอแน่ แก้เป็น list ต่อ index ให้เหมือน `plan.py`

## Decisions ที่ ticket นี้ยืนอยู่

- **`SIG-D04`** executor เป็น state machine บริสุทธิ์ใน `control/` คืนคำสั่งเป็นข้อมูล และมีโมดูลเดียวใต้
  `simulation/sumo/` ที่เอาคำสั่งไปใช้จริง ทำไมต้องแยกแบบนี้: executor จะได้ทดสอบได้โดยไม่ต้องเปิด
  SUMO และตรวจได้ด้วยเครื่องว่ามีที่เปลี่ยนไฟได้ที่เดียว ตัวควบคุมไม่เคยเห็นคำสั่งเหล่านี้
- **`SIG-D08`** การรันแบบ `none` ต้องได้ผลตรงกับก่อนมี M2 ทุกไบต์ใน "ชุด artifact ของ M1"
  ตาราง `signal_event` อยู่นอกชุดนั้นโดยนิยาม (test golden digest ยกเว้นไว้แล้ว) ดังนั้นการเพิ่มตารางว่าง
  ต้องไม่ทำให้ golden digest เปลี่ยน ถ้าเปลี่ยน แปลว่าเราไปแตะอะไรที่ไม่ควรแตะ

## ศัพท์

- **executor**: ตัวกลางระหว่างคำขอของตัวควบคุมกับ SUMO ตัดสินว่าเปลี่ยนไฟได้เมื่อไหร่อย่างถูกกฎ
- **command** (`SignalCommand`): คำสั่งที่ executor คืนออกมาเป็นข้อมูล ยังไม่ได้ทำอะไรกับ SUMO
- **write site**: จุดในโค้ดที่สั่งเปลี่ยนไฟใน SUMO จริง ๆ ต้องมีจุดเดียว
- **signal event**: บันทึกหนึ่งแถวของการตัดสินใจหนึ่งครั้งของ executor (ขอ, เลื่อน, แทนที่, เริ่มเปลี่ยน,
  เข้า stage, ถูกบังคับเพราะ max green, ปฏิเสธ)
- **stage**: phase ที่ให้รถวิ่งได้ ตัวควบคุมขอได้เฉพาะ stage ส่วนไฟเหลืองเป็น **transition phase**
  ที่ขอเองไม่ได้
- **link index**: ตำแหน่งหนึ่งในสตริงไฟของแยก หนึ่งตำแหน่งอาจคุมการเชื่อมต่อหลายเส้น
- **golden digest**: ลายนิ้วมือของไฟล์ผลลัพธ์จากการรัน `none` ที่บันทึกไว้ก่อน M2 ใช้จับว่ามีอะไรเปลี่ยนโดยไม่ตั้งใจ

## สิ่งที่สร้างเสร็จแล้ว

- `simulation/sumo/signal_writer.py`: `apply_signal_commands(binding, commands)` เป็นจุดเดียวที่เรียก
  `trafficlight.setPhase` / `setPhaseDuration` และส่งคำสั่งตามลำดับที่ได้รับ ไม่สลับลำดับเอง
- `SumoConnection.apply_signal_commands(commands)` คือทางที่ run loop ใช้ส่งคำสั่ง (P2-03 จะเป็นคนเรียก)
- `RunRecorder.record_signal_events(events)` กับตาราง `state/signal_event.parquet` แถวในตารางเรียงตาม
  `(time_s, intersection_id)` แต่แถวของ executor ตัวเดียวกันใน tick เดียวกันยังเรียงตามลำดับเดิม การรันแบบ
  `none` จะได้ตารางว่างที่มีคอลัมน์ครบ
- `SCHEMAS` เปลี่ยนเป็น public และแก้ไขไม่ได้แล้ว ส่วน `tls_program.parquet` เก็บทุกการเชื่อมต่อที่อยู่หลัง link index เดียวกันครบแล้ว
- architecture test `test_only_the_signal_writer_sets_a_traffic_light` ล็อกให้มีไฟล์เดียวที่เปลี่ยนไฟได้

## สิ่งที่วัดได้จาก SUMO จริง

- `SetPhase(A0, 1)` มีผลตั้งแต่ step ถัดไปทันที
- `SetRemainingDuration_s` นับเวลาจาก **ตอนที่สั่ง** ไม่ได้นับจากต้น phase ตัวอย่าง: สั่ง 20 s ตอน t=10
  จะยังเป็น phase 0 ที่ t=30 และเปลี่ยนเป็น phase 1 ที่ t=31 ผลตรงกันทั้ง traci และ libsumo
  ที่ช้ากว่าที่คิดไปหนึ่ง step คือคำถามเรื่อง zero-margin race ของ P2-03
- สั่งยืดเป็น 61 s แล้ว stage 0 อยู่เลย 42 s ไปได้จริง ส่วนการรันที่ไม่สั่งอะไรจะออกจาก stage 0 ไปแล้วก่อน t=50

## รันและตรวจยังไง

```
rtk proxy make check
uv run pytest tests/simulation/sumo/test_signal_writer.py -q   # fake binding + SUMO ทั้งสอง binding
uv run pytest tests/test_architecture.py -q                     # write-site fence
uv run pytest tests/simulation/sumo/test_golden.py -q           # การรัน none ยังตรงกับ golden ทุกไบต์
```

## ยังไม่ได้ทำ และขั้นต่อไป

- ยังไม่มีอะไรเรียก executor ระหว่างการรันจริง `cadence run` ยังเหมือนเดิมทุกอย่าง
- architecture test จับได้เฉพาะการเรียกแบบ `x.trafficlight.setY(...)` ตรง ๆ ถ้าตั้งชื่อเล่นให้ `trafficlight`
  หรือเรียกผ่าน `getattr` จะจับไม่ได้ เป็นข้อจำกัดแบบเดียวกับ test ห้าม import ที่มีอยู่เดิม
- ขั้นต่อไปคือ **P2-03**: ให้ request schedule ขับ executor บนการรันจริง พิสูจน์ว่าไฟเหลืองครบเวลาเสมอ
  และวัด zero-margin race ว่าใครชนะกันที่ step สุดท้ายของไฟเหลือง ระหว่างการเปลี่ยนไฟเองของ SUMO กับ `SetPhase` ของ executor
