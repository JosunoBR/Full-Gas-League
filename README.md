# 🏎️ Full Gas League — Sim-Racing Championship Platform

[![Status](https://img.shields.io/badge/Status-Active%20Production-success?style=flat-square)]()
[![Stack](https://img.shields.io/badge/Stack-Web%20%7C%20Mobile%20%7C%20APIs%20%7C%20Database-blue?style=flat-square)]()
[![Platform](https://img.shields.io/badge/Platform-Web%20%7C%20Android-orange?style=flat-square)]()

A comprehensive management ecosystem built to organize, score, and track virtual Formula 1 and sim-racing tournaments. Designed to automate race operations, replace manual spreadsheet calculations, and provide real-time standings for drivers and teams across **Web and Mobile platforms**.

---

## 🎯 The Problem & The Solution
* **The Problem:** Managing a racing league requires handling driver sign-ups, calculating race classifications, applying penalty points, tracking team constructors' points, and posting updates manually across groups. League members need instant access to standings, schedules, and race results—not just through a web browser.
* **The Solution:** A centralized digital ecosystem featuring a web platform for administrators and an Android mobile app for community pilots. Automates point computation, stores telemetry/race outcomes, and provides real-time access to standings, schedules, and detailed statistics.

---

## ✨ Key Features

### 🌐 Web Platform
- **Championship Engine:** Automatic points distribution based on race finishes, pole positions, and fastest laps.
- **Driver & Team Management:** Complete historical stats, podium tracking, and telemetry overviews.
- **Administrative Dashboard:** Manage seasons, grids, penalties, and event schedules.
- **Rulebook & Announcements Hub:** Publish official rules, penalty notices, and announcements.
- **Dynamic Leaderboards:** Instant updates to Driver and Constructor standings post-race results.

### 📱 Android Mobile App
- **Live Standings:** View real-time driver and constructor classifications by grid/season.
- **Race Calendar:** Upcoming events, race dates, and session schedules.
- **Detailed Race Results:** Access race summaries, final positions, fastest laps, and penalty details.
- **Driver Profiles:** View pilot statistics, career records, and personal achievements.
- **Push Notifications:** Stay updated with race announcements and standing changes.

---

## 🛠️ Architecture & Tech Stack

### Backend / APIs
- **Framework:** Flask (Python)
- **Business Logic:** RESTful API with JWT authentication for mobile and web clients.
- **Database:** Relational database (PostgreSQL/SQLite) modeling drivers, seasons, tracks, teams, and race results.
- **Hosting:** PythonAnywhere with custom domain support.
- **CORS:** Enabled for cross-origin requests from mobile and external clients.

### Web Frontend
- **Technologies:** HTML5, CSS3, JavaScript, Jinja2 templates.
- **Architecture:** Responsive design with separate admin and public portals.

### Android Mobile App
- **Language:** Kotlin/Java
- **API Integration:** Consumes REST endpoints for standings, calendar, race results, and driver profiles.
- **Features:** Offline caching, push notifications, and intuitive navigation.

---

## 📡 API Endpoints

The platform exposes a comprehensive REST API (`/api`) for mobile and external integrations:

### Public Endpoints (GET)
- `GET /api/news` — Latest news from the carousel.
- `GET /api/standings/<grid>` — Driver standings by grid/category.
- `GET /api/constructor-standings/<grid>` — Constructor championship standings.
- `GET /api/calendar/<grid>` — Race schedule and events.
- `GET /api/race/<id>/results` — Detailed race results and summary.
- `GET /api/pilots` — List of active drivers with profiles.
- `GET /api/teams` — List of active teams.

### Authentication
- Token-based authentication (JWT) for admin endpoints.
- Mobile app authenticates via credentials and receives bearer tokens.

---

## 🎮 Mobile App Features

### Current Implementation
- **Real-time Standings Sync:** Race results update instantly on the mobile app.
- **Offline Support:** Cached standings and previous results available offline.
- **Push Notifications:** Drivers receive alerts for race updates and announcements.
- **Customizable Filters:** View standings by grid, season, or team.

### Architecture
- Native Android app consuming `/api` endpoints.
- Local database caching for improved performance.
- Background services for notification delivery.

---

## 💻 Web Platform Administration

### Core Business Logic
The system uses **dynamic point calculation**:
- **Race Points:** Distributed based on grid size (20 or 22 drivers).
  - Standard (20 drivers): P1 (35pts) → P20 (1pt)
  - Full grid (22 drivers): P1 (35pts) → P22 (1pt)
- **Penalties:** Court penalties and warnings automatically deducted from standings.
- **Conduct System (CNH):** Global 25-point conduct rating with deductions for protests, warnings, and no-shows.

### Team & Reserve System
- **Team Championship:** Up to 3 drivers per team + 4 official reserves.
- **Driver Championship:** Individual-focused with optional team secondary classification.
- **Reserve Pool:** Unlimited reserve listing with flexible substitutions.
- **Per-Grid Profiles:** Drivers can have different profile photos per grid.

### Reverse Grid System
- Applied in driver championships for vehicle balance.
- Automatic car allocation based on constructor classification standings.

---

## 🚀 Deployment & Hosting

### Production Environment
- **Hosting:** PythonAnywhere with automatic reload on updates.
- **Custom Domain:** `www.fullgasleague.com.br` with DNS CNAME configuration.
- **Database Backups:** Regular automated backups via PythonAnywhere panel.

### Update Process
1. Push changes: `git push origin main`
2. Pull on server: `cd ~/Full-Gas-League && git pull origin main`
3. Reload app via PythonAnywhere Web tab.

---

## 🔄 Maintenance & Tools

### Scripts
Located in the project root for auditing and data migration:
- `verificar_pontos.py` — CNH audit across all drivers.
- `corrigir_pontos.py` — Sync CNH balances from protest history.
- `estornar_punicoes.py` — Revert punitions to dynamic model.
- `migrar_fotos_grid.py` — Migrate grid photos from names to IDs.
- `reparar_fotos_grid.py` — Fix photo references by season.

### Testing
```bash
python -m unittest tests/test_home_consistency.py
python -m unittest tests/test_constructor_scoring.py
```

---

## 📋 Code Standards

### Database Access Pattern
```python
# Safe record retrieval with 404 handling
protesto = db.session.get(Protesto, protest_id) or abort(404)
```

### Model Serialization
All models implement `to_dict()` for JSON conversion in API responses.

---

## 📂 Project Structure

```
Full-Gas-League/
├── app/
│   ├── routes/          # Web & API endpoints
│   ├── templates/       # Jinja2 HTML templates
│   ├── static/          # CSS, JS, images, uploads
│   ├── models.py        # Database schemas
│   ├── utils.py         # Helpers & scoring tables
│   └── services/        # Domain logic (scoring, diagnostics)
├── tests/               # Unit tests
├── scripts/             # Maintenance & migration tools
└── run.py              # Flask app entry point
```

---

## 📱 Mobile App Repository

The Android app is maintained separately with full integration to the backend API. Features include native UI, offline caching, and push notification support.

---

## 🔒 Source Code Notice

*Core business logic, production environment variables, and proprietary tournament assets remain private to protect league infrastructure and member privacy. This repository showcases architecture, database schemas, API design, and public interface modules.*

---

## 📞 Contact & Community

- **Instagram:** [@fullgasleagueofficial](https://www.instagram.com/fullgasleagueofficial/)
- **YouTube:** [@FullGasLeagueF1Oficial](https://www.youtube.com/@FullGasLeagueF1Oficial)
- **Email:** fullgasracingf1@gmail.com

**Developed by:** Josué Nogueira
