# 🦺 Construction Site PPE Monitoring System

## 📌 Overview
This project is an **AI-powered safety monitoring system** designed for construction sites. It uses **computer vision (YOLOv8)** to detect workers and verify compliance with **Personal Protective Equipment (PPE)** such as helmets and safety vests.

The system helps improve workplace safety by automatically detecting violations and providing real-time monitoring and analytics.

---

## 🎯 Objectives
- Detect workers on construction sites
- Identify PPE compliance:
  - ✅ Helmet / ❌ No Helmet  
  - ✅ Safety Vest / ❌ No Vest  
- Detect animals (for safety risks)
- Capture violation images
- Provide real-time monitoring & statistics

---

## 🧠 System Architecture
Camera
↓
AI Engine (YOLOv8)
↓
Rule Engine
↓
Backend API
↓
Database
↓
Dashboard (Admin)

---

## 🚀 Features

### 🔍 AI Detection
- Person detection using **YOLOv8**
- PPE detection:
  - Helmet / No Helmet
  - Safety Vest / No Vest
- Animal detection (unexpected hazards)

### 📸 Image Capture
- Automatically capture images when:
  - PPE violation detected
  - Unknown person detected
- Store images for audit & review

### ⚙️ Rule Engine
- Define safety rules  
  Example: IF person AND (no helmet OR no vest) → violation

- Trigger alerts when rules are violated

### 🖥️ Desktop Application
- Real-time camera monitoring
- Display detection results
- Capture and send data to backend

### 🌐 Admin Dashboard
- Rule Management
- Image Monitoring
- Statistics & Reports
- Violation tracking

---

## 🏗️ Tech Stack

### AI / Computer Vision
- YOLOv8 (Ultralytics)
- Python
- OpenCV

### Backend
- .NET (ASP.NET Core Web API)
- RESTful API
- JWT Authentication (optional)

### Frontend (Admin)
- React / Razor Pages

### Desktop App
- .NET (WPF / WinForms)

### Database
- SQL Server / PostgreSQL

---

## 📂 Project Structure
/ai-engine # YOLOv8 detection service (Python)
/backend # ASP.NET Core API
/frontend # Web admin interface


