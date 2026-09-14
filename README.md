# Intelligent AI-Powered Circular Campus Resource Exchange and Asset Life Cycle Management System

**Working name:** Campus Item Exchange

A small university website where one department lists an unused item, another department requests it, and an administrator approves the transfer. The website also records maintenance and final disposal and provides simple AI assistance.

**Course:** COSC 336 Introduction to Software Engineering  
**Status:** Phase 1 planning and requirements gathering  
**Repository:** [cosc336-circular-campus-9](https://github.com/HamedQayed/cosc336-circular-campus-9)  
**License:** MIT, as stated in the original team README; confirm the repository LICENSE file matches.

The functions below are planned features. This README does not claim they have already been implemented.

## Project scope

One campus, two sample departments, about 20 sample items, and three user roles: staff, asset custodian, and administrator. Initial demonstration items will be chairs, books, and monitors. Other campus asset categories can use the same registration fields.

The main pages will cover the item list and registration form, requests and approvals, item history, and the assistant and reports, with a separate login screen.

The prototype will use sample data. Public sales, online payments, physical delivery services, and automatic asset disposal are outside the proposed software scope. University-system integrations, wider campus rollout, and historical demand prediction will be considered during feasibility and detailed requirements review. The full course project description determines any additional mandatory scope.

## Core features

| ID | Feature | Planned behavior |
| --- | --- | --- |
| FR01 | Asset registration and publication | Custodians shall add and edit item name, description, category, condition, quantity, department, custodian, and location. They shall mark surplus or underused items as available for others to request. |
| FR02 | Search requests and reservations | Staff shall search and filter available items and submit a request with specifications, quantity, urgency, and needed date. The system shall show request status, support reservations, and prevent reservations or approved allocations from exceeding available quantity. |
| FR03 | Approvals and transfers | Administrators shall approve or reject requests and record a reason. Custodians shall confirm completed handovers. The system shall update ownership, custody, location, and availability only after the required approval and handover steps, and retain the transfer record. |
| FR04 | Asset life cycle history | Custodians shall record inspections, maintenance, repairs, refurbishment, donation, recycling, and disposal with the date, responsible person, outcome, and relevant cost. Administrators shall approve transfers and final disposition actions. Records shall preserve the history of each item. |
| FR05 | User roles and permissions | Users shall sign in under staff, custodian, or administrator roles. Staff shall manage their own requests; custodians shall manage assigned assets; administrators shall manage accounts and approvals. The system shall enforce these permissions and log important changes. |

## Required AI features

All five AI functions remain in the project. We propose one hosted AI service used through a small Python helper module.

| ID | Feature | Planned behavior |
| --- | --- | --- |
| AI01 | Resource matching | The system shall suggest up to three available items for a request using meaning, technical compatibility, condition, quantity, location, and urgency. Each suggestion shall include a short reason. The application shall check availability and permissions, and the requester shall choose whether to proceed. |
| AI02 | Asset classification | The system shall suggest an item category, tags, and a clearer description from the entered information. The custodian shall review or edit the suggestion before saving it. Unknown specifications shall remain unknown. |
| AI03 | Sustainability advice | The system shall suggest reuse, transfer, repair, refurbishment, donation, recycling, or retirement using the available condition, demand, cost, and environmental information. It shall explain the suggestion and identify missing information. Authorized staff shall make the final decision. |
| AI04 | Natural language assistant | The system shall answer simple questions about authorized asset records, help users search, prepare a resource request, and find the correct page. A user shall confirm a request before it is submitted. The assistant shall follow the same permissions as the normal interface. |
| AI05 | Generated activity reports | The system shall produce a short written summary of exchanges, maintenance, avoided purchases, savings, waste diversion, and estimated carbon reductions. Application code shall calculate totals; AI shall summarize those totals. Sample data, assumptions, and unavailable estimates shall be clearly identified. |

The application will calculate quantities and report totals and enforce permissions and approvals. AI suggestions require user review. If the AI service is unavailable, ordinary search, requests, and asset records will remain usable.

## User roles and stakeholders

| Login role | Main permissions |
| --- | --- |
| Staff | Browse items, submit and track their own requests, and use the assistant. |
| Asset custodian | Maintain assigned item records, publish availability, confirm handovers, and record inspection and maintenance events. |
| Administrator | Manage accounts, approve requests and final disposition, and view activity and sustainability reports. |

Departments and requesters use the staff role. Asset owners and Facilities/IT staff use the custodian role for assigned items. Finance, sustainability staff, management, and auditors are report recipients during the prototype. Donation and recycling partners receive approved handover details; campus staff record their confirmations. These groups remain stakeholders even when they do not have a separate login role.

## Proposed technology

- **Application:** Python with Flask.
- **Pages:** HTML templates and CSS served by the same application.
- **Database:** SQLite for the small local prototype.
- **AI:** One hosted service, selected after checking access, cost, and data handling.
- **Testing:** Python tests for critical workflows plus manual usability checks.
- **Collaboration:** Git and GitHub.

This is a proposal for Phase 2 feasibility review. SQLite avoids a separate database server for the prototype; see the [official Flask database tutorial](https://flask.palletsprojects.com/en/stable/tutorial/database/). The [Flask project layout guide](https://flask.palletsprojects.com/en/stable/tutorial/layout/) shows how templates, application modules, and tests can be kept together. Exact versions and run commands will be added after the application is built and tested.

## Course phases and deadlines

Each deadline is during the scheduled lab in the week beginning on the date shown.

| Phase | Lab week beginning | Deliverable | Weight |
| --- | --- | --- | --- |
| 1 | 14 September 2026 | Initial plan and requirement gathering document | 10% |
| 2 | 21 September 2026 | Feasibility document | 10% |
| 3 | 5 October 2026 | Requirements document | 10% |
| 4 and 5 | 26 October 2026 | Architecture and detailed design document | 20% |
| 6 | 16 November 2026 | Draft implementation with major features | 20% |
| 7 | 23 November 2026 | Details of test cases | 10% |
| 8 | 23 November 2026 | Final project, presentation, and demonstration | 20% |

**GitHub deadline:** Add the instructor and lab engineer as collaborators by **15 September 2026**. Each member must make regular, meaningful commits under their own identity. GitHub history accounts for **10% of each student's phase grade**.

## Proposed success criteria

These are prototype acceptance targets to confirm with stakeholders, not achieved results or real campus savings.

| Measure | Target |
| --- | --- |
| Core functions | Pass all 10 agreed critical test scenarios, covering registration, search, reservations, approvals, transfers, permissions, and life-cycle events. |
| Search performance | At least 19 of 20 searches return within 3 seconds using the 20-item sample database on the agreed test computer. |
| User acceptance | At least 4 of 5 representative test users submit an item request without assistance. |
| Match usefulness | For at least 8 of 10 test requests with a valid match, a reviewer finds a suitable item among the top 3 AI suggestions. Compare results with keyword search. |
| Avoided purchases | Record 5 sample transfers that replace hypothetical planned purchases and correctly calculate net savings for all 5. |
| Reuse repair and sustainability | Demonstrate at least 2 reuse cases and 2 repair cases. For 10 sample reporting cases, match manually checked reuse, waste-diversion, and carbon calculations wherever inputs exist; flag missing inputs. |

For reporting, use net savings = avoided purchase cost minus transfer, repair, and refurbishment costs. Report reuse rate and waste diversion for a stated period using unique assets so repeated events are not double-counted. Carbon reduction is the replacement-scenario emissions minus reuse-scenario emissions; show the source and assumptions for each factor. A missing input produces an unavailable estimate, not an invented value. Any demonstration factors are labeled as sample assumptions.

## Phase 1 documentation and setup

Phase 1 produces one **Initial Plan and Requirement Gathering Document** covering the introduction, overview, stakeholders, gathering methods and findings, initial requirements, success measures, and project plan. Interview notes must describe actual consultations; unconfirmed procedures remain assumptions.

1. Clone the team repository:

```bash
git clone https://github.com/HamedQayed/cosc336-circular-campus-9.git
cd cosc336-circular-campus-9
```

2. Add the revised README at the repository root.
3. Place the report at `docs/phase1/Phase_1_Initial_Plan_and_Requirements.docx`, creating the folder if needed. Keep any actual interview notes alongside it.
4. Assign team roles, record stakeholder findings, and review the complete course project description.
5. Commit each completed contribution using its author's own Git identity.

Application installation and startup instructions will be added when working code is available.

### Planned organization

These locations describe the intended structure; they are not a claim that the files already exist.

| Location | Purpose |
| --- | --- |
| `README.md` | Project scope, schedule, and setup information. |
| `docs/phase1/` | Phase 1 report and actual gathering notes. |
| `docs/phase2/` | Feasibility document. |
| `docs/phase3/` | Detailed requirements. |
| `docs/design/` | Architecture and detailed design for Phases 4 and 5. |
| `app/` | Python application, templates, styles, and AI helper. |
| `tests/` | Tests for implemented behavior. |
| `sample_data/` | Clearly labeled demonstration data. |

## Team workflow

- Assign each task an owner and a reviewer. Team members may hold more than one responsibility.
- Use a branch for a task and make small, meaningful commits.
- Open a pull request and have a teammate review it before merging.
- Check relevant behavior and update the documentation with each change.
- Keep passwords, API keys, local databases, and generated files out of Git.
- Review any AI-generated work and follow the course policy for disclosing assistance.

**Team members and student IDs:** [Fill in]  
**Task assignments:** [Fill in]  
**Instructor GitHub username:** [Fill in]  
**Lab engineer GitHub username:** [Fill in]  
**Consultation notes and dates:** [Fill in with actual findings]

## References

- COSC 336 Circular Campus Project Fall 2026, slides 4 to 11 and accompanying notes.
- Git, GitHub, and Copilot for Senior Design onboarding guide.
- Official Flask documentation linked above.

**Last updated:** 14 September 2026
