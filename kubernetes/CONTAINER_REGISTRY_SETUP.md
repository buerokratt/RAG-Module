# Container Registry Setup Guide

This guide explains what components need to push to gcr 

## Overview

The RAG Module consists of multiple container images that need to be pushed to your container registry. Currently, we use ECR for testing, but you should push images to your own registry before deployment.



## Step 1: Build Container Images

Build all required images from the repository root:

### **1.1 GUI (Frontend)**

```bash
cd GUI
docker build -t rag-module/gui:latest -f Dockerfile.dev .
cd ..
```

update the GUI helms values image: repository section with actual image

### **1.2 LLM Orchestration Service**

```bash
docker build -t rag-module/llm-orchestration-service:latest -f Dockerfile.llm_orchestration_service .
```
update the LLM Orchestration Service helms values image: repository section with actual image (there are two places to update in this file)

### **1.3 Authentication Layer**



