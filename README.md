# 🎓 College Resell Platform

A peer-to-peer product reselling web platform for college students, enabling easy buying, selling, and requesting of items within the campus. Built using **Flask**, **MongoDB**, and **Cloudinary**, with secure Google OAuth login and admin approval features.

## 🔗 Live Demo

🌐 [resellnitrr.me](https://www.resellnitrr.me/) *(Deployment: Render)*

> ⚠️ *Note: If you open the site in Chrome, you may receive a warning from Google Safe Browsing. A re-verification and security update may be in progress.*

---

## 🛠️ Tech Stack

- **Backend:** Python (Flask), Flask-PyMongo
- **Frontend:** HTML, CSS, Bootstrap, JavaScript
- **Database:** MongoDB Atlas
- **Authentication:** Google OAuth (Authlib)
- **Media Storage:** Cloudinary
- **Deployment:** Render

---

## 📦 Features

### 👤 Google Login
- Secure login using your Google account
- User session management using Flask `session`

### 🛒 Buy Section
- Browse all available products listed by students
- Filter by categories (Electronics, Groceries, etc.)
- View product details (description, images, contact info)
- Request items if not found

### 📤 Sell Section
- List your items for sale with images and details
- Upload product photos via Cloudinary
- Only visible after admin approval

### ✅ Admin Panel
- Approve or reject listings and wanted item requests
- Admin identified by a specific Google email (e.g. `admin@example.com`)

### 🔍 Wanted Items
- Buyers can request products they’re looking for
- Sellers can view requested items to fulfill

### 📝 My Listings & My Wanted Items
- Sellers can:
  - View & edit their own product listings
  - Mark items as sold
- Buyers can:
  - Edit or mark wanted items as fulfilled

---
