# Milky Shaky Drinks E-Commerce Platform

## 🥤 Project Overview

Milky Shaky Drinks is a Flask-based web application designed to manage custom milkshake orders, from user registration and dynamic order placement to payment processing and administrative reporting. It utilizes an SQL database (SQLite in development) for persistent storage and incorporates modern features like role-based access control (RBAC) and dynamic lookup management.

## Technology Stack

| Component        | Technology / Implementation     | Notes                                                                 |
|------------------|----------------------------------|-----------------------------------------------------------------------|
| **Backend**       | Flask, Python 3                  | Main application logic and routing.                                   |
| **Database**      | SQLite3 / Flask-SQLAlchemy       | Used for persistent data storage in development.                      |
| **Authentication**| Flask-Login, Flask-Bcrypt        | Secure user sessions and password hashing.                            |
| **Styling**       | Tailwind CSS (CDN)               | Used for all frontend design and responsiveness.                      |
| **Payment Gateway** | Payments (Simulated)     | Hosted Checkout flow implemented via a POST redirect.                 |
| **Async Tasks**   | Python `threading`               | Sends emails in the background to prevent blocking web requests.      |

## 📽️ Application Preview (Video Snippets)

Below are short video snippets demonstrating the application's core functionality, following a typical user journey.

---

### 1. User Registration and Login
<video src="assets/videos/1.mkv" width="640" controls></video>
