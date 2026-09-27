# Pakistani Real Estate Voice Agent

**An UrduLish-speaking AI voice agent for Pakistani real estate — searches properties, checks prices, and books site visits on Google Calendar with email confirmations.**

[![Tests](https://img.shields.io/badge/tests-775%20passing-brightgreen)]()
[![Security](https://img.shields.io/badge/security-127%2F127%20blocked-blue)]()
[![Python](https://img.shields.io/badge/python-3.12-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## Table of Contents

- [Overview](#overview)
- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Project Timeline](#project-timeline)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Usage](#usage)
- [Testing](#testing)
- [Security](#security)
- [Data](#data)
- [Known Limitations](#known-limitations)
- [Project Structure](#project-structure)
- [Documentation](#documentation)

---

## Overview

Most real estate chatbots are English-only and just answer questions. This agent speaks **UrduLish** — the natural mix of Roman Urdu and English that urban Pakistanis actually use — and can **book real site visits** with Google Calendar integration.

**Example interaction:**

> **User:** *"Lahore mein 3 bedroom house chahiye"*
>
> **Agent:** *"Ji sir, Lahore mein 36 listings hain. Sabse sasti LAH-0013 hai, Hamza Town mein, 3-bedroom, 59 lakh. Kya aap site visit book karna chahenge?"*
>
> **User:** *"Haan, book kar do"*
>
> **Agent:** *"Theek hai, konsa din aur waqt theek rahega?"*

The agent handles the full flow: greeting → search → price check → recommendation → booking → confirmation email.

---

## What It Does

### Core Capabilities

| Feature | Description |
|---|---|
| **Property Search** | Natural language search across 575 real listings in 4 cities |
| **Price Lookup** | Exact pricing from structured database (SQL, not hallucinated) |
| **Amenity Filter** | "Furnished with basement in DHA" → filtered results |
| **Aggregate Queries** | "Average price in Karachi", "Cheapest 3-bed in Lahore" |
| **Site Visit Booking** | Real Google Calendar event + email confirmation |
| **Multi-turn Conversation** | Remembers context across turns |
| **Human-in-the-loop** | Confirms before booking — never books without approval |
| **UrduLish Output** | Natural Roman Urdu + English mixed speech |
| **Interruption Handling** | Stops speaking within 0.15s when user interrupts |

### What It Refuses

The agent politely refuses (with a clear message) when asked:
- Prices in non-PKR currencies (no USD conversion data)
- Properties that don't exist (`LAH-9999`)
- Off-topic questions (weather, cricket scores, news)
- Personal info extraction (API keys, other users' data)
- Speculative questions ("best property to invest in?")

---

## Architecture
