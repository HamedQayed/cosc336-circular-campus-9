# Intelligent AI-Powered Circular Campus Resource Exchange and Asset Lifecycle Management System

An enterprise-grade platform for sharing, managing, and optimizing the lifecycle of campus resources—combining traditional asset management with AI-driven semantic matching, sustainability optimization, and intelligent recommendations.

**Project Type:** COSC 336 Software Engineering Team Project  
**Status:** Phase 1 - Requirements & Planning  
**License:** MIT

---

## 🎯 Project Vision

Universities routinely purchase thousands of assets—furniture, computers, lab equipment, materials—while similar usable resources sit unused or are discarded elsewhere. The problem isn't a shortage of reusable assets; it's the absence of an **integrated system that can identify, classify, match, transfer, maintain, and track** those resources throughout their lifecycle.

This project addresses that gap by building a **dual-perspective system**:
- **Classical approach:** Structured, rule-based asset management (requirements, design, modular code, systematic testing)
- **Modern approach:** AI-augmented decision-making (semantic matching, sustainability optimization, natural language interfaces, predictive analytics)

By working on both perspectives, the team will explore how traditional software engineering practices evolve when enhanced with emerging AI technologies—and learn to think critically about when AI adds value versus when human oversight is essential.

---

## 🚀 Core Features (Baseline + AI-Enhanced)

### Baseline Functionality
- **Asset Registry:** Register, catalog, and maintain campus resource records
- **Resource Discovery:** Search, filter, and browse available assets
- **Request Workflow:** Submit resource requests with approval routing and tracking
- **Lifecycle Management:** Record inspections, maintenance, repairs, transfers, donations, recycling, and disposal
- **Access Control:** Multi-role permissions (departments, custodians, admins, facilities, finance)
- **Ownership & Location Tracking:** Manage custody changes and geographic distribution

### AI-Powered Enhancements
- **Semantic Resource Matching Engine:** Intelligently match available assets to departmental requests based on technical specs, condition, quantity, location, and urgency
- **Auto-Classification:** AI-assisted tagging and standardized descriptions for new resources
- **Sustainability Optimizer:** Decision support for reuse, repair, donation, recycling, or retirement
- **Natural Language Assistant:** LLM-powered search and navigation
- **Analytics & Reporting:** Quantify avoided purchases, financial savings, waste diversion, and carbon emission reductions

---

## 📋 Project Structure

```
.
├── README.md                       # This file
├── LICENSE                         # MIT License
├── docs/
│   ├── phase1/                     # Phase 1 deliverables
│   │   ├── 01-project-overview.md
│   │   ├── 02-stakeholder-analysis.md
│   │   ├── 03-process-mapping.md
│   │   ├── 04-requirements.md
│   │   ├── 05-success-criteria.md
│   │   ├── 06-project-plan.md
│   │   └── 07-risk-register.md
│   ├── architecture/               # System design (Phase 2)
│   ├── api/                        # API documentation
│   └── user-guides/                # End-user documentation
├── backend/                        # Backend services (Node/Python/etc.)
├── frontend/                       # Web interface (React/Vue/etc.)
├── ai-modules/                     # AI/ML components
└── tests/                          # Test suites

```

---

## 📊 Phase Breakdown

| Phase | Focus | Timeline |
|-------|-------|----------|
| **Phase 1** | Requirements, stakeholder analysis, process mapping, success criteria, project plan | Weeks 1–2 |
| **Phase 2** | System architecture, data modeling, UI/UX design, tech stack finalization | Weeks 3–4 |
| **Phase 3** | Backend development, API implementation, database design | Weeks 5–7 |
| **Phase 4** | Frontend development, integration testing, AI module prototyping | Weeks 8–10 |
| **Phase 5** | System testing, documentation, deployment preparation, demo & evaluation | Weeks 11–12 |

---

## 🎓 Learning Objectives

By completing this project, students will:
- Apply the **complete software development lifecycle** (requirements → design → implementation → testing → deployment)
- Practice **stakeholder-driven requirements gathering** and user-centered design
- Design and implement a **multi-role access control system** with clear workflows
- Build a **scalable, modular architecture** for a production-grade platform
- Integrate **emerging AI technologies** responsibly into traditional software systems
- Measure **quantifiable business and environmental impact** (cost savings, waste diversion, carbon reduction)
- Reflect critically on **when AI adds value** and when human oversight is necessary
- Collaborate as an **agile engineering team** using GitHub, kanban boards, and code review practices

---

## 👥 Key Stakeholders

| Stakeholder | Role | Needs |
|-------------|------|-------|
| **Departments** | Resource requesters | Find, reserve, and request needed assets quickly |
| **Asset Custodians** | Resource owners | Track asset location, condition, custody changes |
| **Administrators** | System operators | Approve transfers, enforce policies, manage workflows |
| **Facilities/IT** | Support team | Log maintenance, record disposals, manage inventory |
| **Finance/Sustainability** | Decision makers | Measure cost savings, waste diversion, carbon impact |

---

## 🔧 Tech Stack (To Be Finalized in Phase 2)

**Candidates under consideration:**
- **Backend:** Node.js + Express, Python + FastAPI, or Java + Spring Boot
- **Frontend:** React, Vue.js, or Angular
- **Database:** PostgreSQL (primary), potentially MongoDB for flexible asset schemas
- **AI/ML:** OpenAI API, Hugging Face transformers, or custom semantic models
- **Deployment:** Docker, Kubernetes (if scaling required), or cloud platforms (AWS, Azure, GCP)
- **Testing:** Jest/Pytest, Selenium, integration test frameworks
- **DevOps:** GitHub Actions, CI/CD pipelines

---

## 🛠️ Getting Started

### Prerequisites
- Git and GitHub account
- Node.js 16+ or Python 3.9+ (depending on tech stack choice)
- Docker (optional, for containerization)
- A code editor (VS Code recommended)

### Phase 1 Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/HamedQayed/cosc336-circular-campus-9.git
   cd cosc336-circular-campus-9
   ```

2. **Read Phase 1 documentation:**
   ```bash
   cd docs/phase1
   # Start with 01-project-overview.md
   ```

3. **Join the project board:** (Link to GitHub Projects board once created)

4. **Contribute to Phase 1 deliverables:** See [CONTRIBUTING.md](CONTRIBUTING.md) (to be created)

---

## 📈 Success Criteria (Preliminary)

**Functional Goals:**
- ✅ Multi-role authentication and access control
- ✅ Full asset lifecycle tracking (create → maintain → dispose)
- ✅ Request-to-approval workflow with audit trail
- ✅ Semantic matching engine (AI-powered)
- ✅ Sustainability impact reporting

**Quantitative Metrics:**
- **Adoption:** >70% of departments using platform within pilot period
- **Reuse Rate:** >60% of surplus assets successfully transferred
- **Cost Avoidance:** Minimum $50K in avoided purchases (simulated/projected)
- **Sustainability:** Minimum 10 metric tons CO₂ equivalent avoided
- **User Satisfaction:** SUS score >70

**Quality Goals:**
- Code coverage: ≥80%
- API response time: <500ms (p95)
- System uptime: ≥99.5%
- Zero critical security vulnerabilities in final release

---

## 📚 Documentation

- **[Phase 1 Deliverables](docs/phase1/)** – Requirements, stakeholder analysis, process maps, success criteria
- **[Project Plan](docs/phase1/06-project-plan.md)** – Milestones, task breakdown, timeline
- **[Architecture](docs/architecture/)** – System design, data models, component diagrams (Phase 2+)
- **[API Reference](docs/api/)** – Endpoint specifications (Phase 3+)
- **[User Guides](docs/user-guides/)** – Administrator and end-user manuals

---

## 🤝 Contributing

This is a team project. All contributions should follow:
1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make changes and commit with clear messages
3. Submit a pull request with description of changes
4. Get code review approval before merging
5. Ensure tests pass and documentation is updated

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## ⚠️ Critical Design Decisions (Under Discussion)

- **AI Confidence & Transparency:** How much confidence in AI recommendations should trigger automation vs. require human review?
- **Sustainability Metrics:** Which methodology should we use to calculate carbon impact and cost avoidance?
- **Data Privacy:** How should we handle sensitive financial and departmental data?
- **Scalability:** Should the system support multi-campus deployments?

These decisions will be refined during Phase 1 and documented in the Architecture phase.

---

## 🏆 Evaluation Criteria

The project will be evaluated on:
- **Requirements & Design:** Clarity, completeness, stakeholder alignment
- **Implementation:** Code quality, modularity, documentation
- **Testing:** Coverage, edge case handling, integration testing
- **AI Integration:** Value delivered by AI features, user experience, explainability
- **Sustainability Impact:** Measurement and reporting of environmental/financial benefits
- **Presentation & Documentation:** Clarity, professionalism, completeness

---

## 📞 Contact & Support

- **Project Lead:** [Team to assign]
- **Issues & Questions:** Use GitHub Issues with appropriate labels
- **Team Communication:** [Slack/Teams channel to be created]
- **Instructors:** [Course coordinator contact info]

---

## 📄 License

This project is licensed under the MIT License—see [LICENSE](LICENSE) for details.

---

## 🌱 Sustainability Note

This platform is designed to promote a **circular economy** on campus by:
- **Maximizing reuse** of existing assets
- **Reducing unnecessary purchases** and waste
- **Extending asset lifespans** through maintenance and repair tracking
- **Measuring environmental impact** in real-time
- **Supporting data-driven sustainability decisions**

By the end of this project, we hope to demonstrate how software engineering can drive meaningful environmental and economic value.

---

**Last Updated:** September 2026  
**Next Review:** End of Phase 1
