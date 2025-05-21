# Agents Guide

Welcome to the Python-based MCP (Model Content Protocol) Application repository. This guide explains how AI agents (and human contributors) can navigate the project, contribute new features, and ensure the functionality meets all specified requirements.

---

## Table of Contents
1. **Purpose of this File**
2. **Referencing the Requirements Outline**
3. **Developing in Python**
4. **Unit Testing and QA**
5. **GUI Integration**
6. **Contribution Process**

---

## 1. Purpose of this File
The instructions in this file enable AI agents, as well as human contributors, to effectively:
- Understand the development processes used in this Python project.
- Follow the design requirements in the [`requirements_outline.md`](./requirements_outline.md).
- Build a complete set of features, including both backend and GUI capabilities.

This file is **not** a set of optional suggestions—it is the **authoritative** guide for how to interact with and extend this repository.

---

## 2. Referencing the Requirements Outline
All new features and enhancements **must** adhere to the [requirements outline](./requirements_outline.md). 

1. **Before starting any coding task**: Read the relevant sections of `requirements_outline.md`.
2. **While implementing**: Continuously verify that your code aligns with each requirement—especially in areas such as:
   - **Gmail label awareness**  
   - **Semantic search**  
   - **Local logging**  
   - **Multi-LLM support**  
   - **Calendar integration**  
   - **Linear integration**  
   - **GUI features**  
3. **After completing a feature**: Review the relevant requirement items to confirm completeness and correctness.

---

## 3. Developing in Python
- **Recommended Version**: Python 3.9+ (or whichever version the repository documentation specifies).
- **Dependencies**: Use `pip` or a virtual environment tool like `venv` or `conda` as appropriate.  
  ```bash
  python -m venv venv
  source venv/bin/activate  # On Linux/macOS
  venv\Scripts\activate     # On Windows
  pip install -r requirements.txt

## 4. Path
- **Ensure to only work inside the MCP folder.**
