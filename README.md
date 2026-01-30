# Smart Hospital

## Basic Details
### Team Name: Code Craft

### Team Members
- **Minnu Lekha V G** - LBSITW
- **Devu L S** - LBSITW
- **Rudra Lakshmi B P** - LBSITW
- **Abhirami S** - LBSITW

### Hosted Project Link
[https://smart-hospital-709984752011.asia-south1.run.app](https://smart-hospital-709984752011.asia-south1.run.app)

### Project Description
Smart Hospital is an AI-powered queue management system designed to eliminate physical waiting lines. It provides patients with live wait-time estimations, dynamic travel alerts via Google Maps, and a digital ticketing system to ensure a seamless healthcare experience.

### The Problem
Traditional hospital waiting rooms are overcrowded, leading to patient frustration, increased risk of infection, and uncertainty regarding consultation times.

### The Solution
Our project, **"Smart Hospital,"** uses real-time data synchronization via Firebase and Google Cloud to allow patients to track their queue position from home and arrive just in time for their appointment.

---

## Technical Details

### Technologies/Components Used

#### Software
- **Languages:** Python 3.13, HTML, CSS, JavaScript
- **Frameworks:** Django (Full Stack)
- **Libraries:** Bootstrap 5, xhtml2pdf
- **Google Technologies:** Google Cloud Run, Firebase Realtime Database, Firebase Authentication, Google Maps Platform
- **Tools:** Visual Studio Code, Google Cloud SDK

### Implementation

#### Software
- **Installation:**
  ```bash
  pip install django firebase-admin google-cloud-run

```

* **Run:**
```bash
python manage.py runserver

```


* **Deploy:**
```bash
gcloud run deploy smart-hospital --source .

```



---

## Project Documentation

### Software

* **Screenshots**
* **Patient Dashboard:** <img width="1348" height="589" alt="image" src="https://github.com/user-attachments/assets/b5fdb73d-f837-47ef-95c6-25d61e154590" />


* **Live Queue Display:** <img width="1356" height="561" alt="Screenshot 2026-01-16 232931" src="https://github.com/user-attachments/assets/97091d86-dbec-4d7f-8904-957a44a87bb9" />

* **Doctor Portal:** <img width="1356" height="589" alt="image" src="https://github.com/user-attachments/assets/9baeecfc-b78b-45a1-b314-1fe9ca6ba154" />



* **Diagrams**
"The platform utilizes a hybrid cloud architecture. When a doctor updates a status, Firebase triggers a sub-second sync across all patient devices, while Google Maps API calculates the optimal 'Leave By' time for the user."
* **Build Photos**
* **Cloud Architecture:** [Insert Screenshot Link]
* **Final Product:** [Insert Screenshot Link]



### Project Demo

* **Video:** [[About Project]](https://drive.google.com/file/d/10ka-ayh--1ISkIG0CGJdMacRefcYy4mo/view?usp=drive_link)
* **Description:** This video demonstrates the end-to-end flow of the Smart Hospital system—from a patient booking a digital token and receiving a Google Maps travel alert, to the doctor managing the live queue via the backend dashboard.

---

## Team Contributions

* **Minnu Lekha V G:** Backend development, Google Cloud integration, AI predictive logic.
* **Devu L S:** Frontend design and UI implementation.
* **Rudra Lakshmi B P:** Documentation, database schema design.
* **Abhirami S:** Testing, bug fixing, and presentation prep.

