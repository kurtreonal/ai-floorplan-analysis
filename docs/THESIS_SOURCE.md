# VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System for Automated Layout and Cost Estimation

**Undergraduate Thesis**

Submitted to the Faculty of the Department of Computer Studies  
Cavite State University - Bacoor City Campus  
City of Bacoor, Cavite

In partial fulfillment of the requirements for the degree  
**Bachelor of Science in Computer Science**

## Authors

- Aldrin E. Generoso
- Kurt Isaiah R. Pascua
- Lester C. Pajarillo
- Angelo Luigi G. Matavia
- Kristian Kyle Elle P. Madridejo

**Date:** May 2027

---

## Manuscript Information

**Title:** VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System for Automated Layout and Cost Estimation

**Prepared under the supervision of:** Ms. Clarissa V. Rostrollo

An undergraduate thesis manuscript submitted to the faculty of the Department of Computer Studies, Cavite State University - Bacoor City Campus, City of Bacoor, Cavite, in partial fulfillment of the requirements for the degree of Bachelor of Science in Computer Science with Contribution No. _____________.

## Introduction

In the modern construction industry, the early stages of residential floor plan analysis and electrical planning are essential but often slowed down by traditional and manual processes. Electrical designers usually rely on static 2D blueprints where they manually trace layouts, identify electrical components, and estimate wiring paths. This method is time-consuming and may lead to errors in material estimation and layout planning, especially when dealing with complex or unclear floor plans.

At VED Electrical Services, these challenges are evident in the current workflow of electrical designers. Based on an interview conducted with Christian Gabuya, an Electrical Designer at VED Electrical Services, manually counting electrical devices such as outlets and switches, as well as measuring wires and roughing-ins, is done manually. This process becomes more difficult and time-consuming, especially for larger projects. For small projects, estimation may be completed within a day; however, for multi-floor structures, the process can take up to three to four days due to the manual computation involved.

In addition, designers rely on basic formulas to estimate wiring lengths, which are more suitable for small-scale projects but may not provide accurate results for larger or more complex structures. Errors in estimation may also occur due to incomplete or unclear details in floor plans. For example, vertical wiring paths or extended routing are not always visible, leading designers to add extra materials to compensate for uncertainties. While this approach helps avoid shortages, it may result in overestimation and increased project costs.

To address these challenges, this study proposes the development of VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System for Automated Layout and Cost Estimation. The system utilizes Computer Vision (CV) to automatically detect and recognize electrical symbols and transform floor plans into interactive 3D models. It also includes automated estimation and cost computation features to improve efficiency and accuracy in electrical planning.

Overall, this study aims to enhance the workflow at VED Electrical Services by reducing manual effort, minimizing errors, and improving visualization through artificial intelligence and 3D technology.

## Statement of the Problem

The study aimed to develop a 3D floor plan analysis and generation system for VED Electrical Services to help them automate their electrical layout and cost estimation. The research used interviews with their electrical designers and engineers, along with a review of their past residential projects, to understand the real-world problems they face every day.

Electrical construction business, counting outlets and measuring wires by hand is a very slow and tiring process. According to the interview with VED Electrical Services, even a simple three-story building takes them three to four days to estimate because they have to count every single switch and outlet one by one. They currently use a manual formula to guess the length of cables, but this often fails for bigger projects because it is not accurate enough. This leads to the question: How can a computer system be used to automatically recognize symbols in a floor plan to save time and prevent human errors in counting?

The challenges extend to work with flat 2D drawings. There are many parts of a building that you cannot see on a flat piece of paper, like when a wire needs to go up from the ground floor all the way to the 7th floor. Because these "hidden" vertical runs are hard to see, the team is forced to just "add extra wires" and "increase the price a bit" just to make sure they don't run out of materials. This guesswork leads to wasted supplies and prices that are sometimes too high for the client. How can a 3D visualization tool help engineers actually see these hidden wire paths so they can give a more honest and accurate estimate?

In addition, VED Electrical Services has a hard time organizing their final reports. Right now, they don't have a way to quickly create a clean table that shows the total quantity and price of materials. They also mentioned that while a new system would be helpful, it needs to be easy to use and allow them to manually edit the design if a client suddenly wants to move an outlet or add a new switch.

Given the concern, there is a need for a tool that can "read" a floor plan, show it in 3D, and automatically calculate the costs. Therefore, the study seeks to answer: How can this new system replace the manual way of estimating at VED Electrical Services to make their work faster, accurate, and professional for their clients?

## Objectives of the Study

Generally, this study aims to develop the VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System to automate the transformation of 2D residential blueprints into interactive 3D floor plans with integrated electrical layout and cost estimation.

Specifically, the study aims to:

1. Identify the operational bottlenecks and manual layouting challenges encountered by electrical designers at VED Electrical Services through field interviews and workflow observations during the Empathize phase of the Design Thinking methodology.

2. Analyze existing Computer Vision (CV) techniques and 3D rendering approaches to determine the most accurate methods for detecting architectural boundaries and standardized electrical symbols from 2D digital blueprints.

3. Develop the system architecture using React.js for the web interface, Three.js for interactive 3D floor plan visualization, and Python-based OpenCV for the AI-driven symbol detection module; utilizing SQL as a centralized repository for symbol legends, 3D metadata, and material pricing.

4. Implement a Spatial Routing Algorithm within the 3D environment to automatically determine the most efficient paths for wires and conduits, accounting for vertical elevations and structural obstructions to minimize material redundancy.

5. Test the system’s core modules by conducting Accuracy Validation on the AI’s symbol recognition (comparing AI counts vs. manual counts) and Unit Testing to ensure the reliability of 3D spatial alignment and SQL-based cost calculations.

6. Evaluate the system’s overall software quality in terms of functional suitability, usability, and performance efficiency using the ISO 25010 standard, involving professional validation from the designers and engineers of VED Electrical Services.

## Theoretical Framework

The theoretical framework is presented through a System Architecture Design. This design illustrates how the system's components, actors, modules, and data flows are organized and interrelated within a web-based environment, providing a structured conceptual basis for the system's design, implementation, and evaluation. The architecture highlights two primary actors, the User and the Admin; six core processing modules; a Python Flask backend API; a MySQL database; and a React.js frontend, all operating over the Internet.

The user represents the project estimator and the admin, who is responsible for maintaining the system's symbol dataset and material pricing database. Each actor has an interaction with specific modules within the system boundary.

The floor plan input module serves as the entry point of the system.

This module accepts a high-resolution digital blueprint or scanned image of a residential floor plan through the React.js interface as the primary data source.

The quality and format of this input directly influence the accuracy of all subsequent processes, reflecting one of the system's operational limitations.

Upon submission, the floor plan image is transmitted to the Python Flask backend API for downstream processing.

The AI image recognition module receives the uploaded floor plan from the Flask backend and applies computer vision techniques to prepare the image for structured analysis. This module serves as the eyes of the system, processing pixel-level data including grayscale conversion, Gaussian blur, noise removal, and binary thresholding. It then employs the Hough Line Transform to extract wall coordinates from the cleaned image before the brain (YOLOv8) does its work.

The Symbol Detection and Classification module identifies and categorizes standard electrical symbols embedded within the floor plan, including power outlets, wall switches, lighting fixtures, and data connection ports. Using a YOLOv8 model trained on annotated floor plan datasets prepared through Roboflow, the module receives the cleaned image output from the AI Image Recognition module and performs processing to detect each symbol's type, position, and bounding box coordinates. Detections below a confidence threshold of 0.5 are filtered out, and the resulting data is structured into a symbol coordinate JSON passed downstream.

The Layout Generation module translates the detected symbol coordinates and wall geometry into rendered visual outputs through a dual-interface rendering engine, Konva.js for the interactive 2D canvas and Three.js for the 3D visualization through 2D-to-3D wall reconstruction.

The Spatial Routing Algorithm applies an A* pathfinding algorithm to compute optimal wiring paths between detected symbols and the electrical panel, calculating total wire lengths in metres while navigating around wall boundaries derived from the AI Image Recognition module.

The Cost Estimation Module receives the detected symbol quantities from the Symbol Detection and Classification module and the total wire lengths from the Spatial Routing Algorithm module. It queries the MySQL pricing database, which contains the company's official material unit costs, to compute an itemized Bill of Materials and total project cost. The Admin actor maintains this pricing database, ensuring that unit costs remain current and accurate. Upon completing the cost computation, the module generates a report output directed to the System Output.

The System Output module consolidates all deliverables produced by the parallel processing branches and presents them to the User through the React.js frontend. An interactive 2D layout with wiring overlay, an interactive 3D visualization through 2D-to-3D wall reconstruction, an itemized Bill of Materials with total project cost sourced from the company’s official pricing, and an exportable PDF report. All system data, including detected symbol records, material pricing, and project history is stored in and retrieved from the MySQL database through the Python Flask backend. Together, these outputs directly address the manual inefficiencies in electrical layout estimation identified in the study's Statement of the Problem, supporting electrical designers and project estimators in streamlining the preliminary stages of residential electrical planning.

The framework visually demonstrates how the system's architecture works, from raw floor plan image input, through AI-driven preprocessing and symbol detection, through parallel 2D-to-3D wall reconstruction and spatial routing, through toggleable visualization with wiring overlay, to final output that provides a clear and technically conceptual basis for the system's design, implementation, and evaluation in the succeeding chapters of this study.

![Figure 1. Theoretical Framework of VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System for Automated Layout and Cost Estimation](images/figure-1-theoretical-framework.png)

*Figure 1. Theoretical Framework of VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System for Automated Layout and Cost Estimation*

## Significance of the Study

The development of “VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System for Automated Layout and Cost Estimation” contributes to the advancement of construction design by addressing the limitations of traditional manual methods in spatial planning, electrical layouting, and material estimation. The findings of this study will be significant to the following:

**For VED Electrical Services.** The proposed system directly improves workflow efficiency in electrical design processes. It supports faster project completion, reduces material wastage, and enhances the accuracy of planning and estimation, which leads to improved operational productivity and significant cost savings for the company.

**For Electrical Designers.** This study automates the generation of electrical and data layouts. Through optimized wiring paths and conduit placement, the system reduces design errors, minimizes manual computation, and supports more accurate material estimation, leading to improved resource management.

**For Architects.** The study enhances the visualization of structural plans by converting flat 2D drawings into interactive 3D models. This capability improves spatial analysis and strengthens coordination between architectural and electrical components, resulting in more precise and integrated design outputs.

**For Future Researchers.** This study provides a foundational framework that can be further enhanced through the integration of advanced machine learning models, real-time simulation, and expansion into large-scale or smart building applications.

## Time and Place of the Study

The research and development of the system, titled "VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System for Automated Layout and Cost Estimation," was conducted from January 2026 to April 2026. The study followed the Design Thinking methodology, covering the transition from technical conceptualization to formal system planning.

The initial phase, spanning January to February 2026, focused on the Empathize and Define stages through academic consultations at Cavite State University - Bacoor Campus. In April 2026, the study transitioned to the Ideation stage through intensive field observations at the VED Electrical Services office in Rodriguez, Montalban, Rizal, where operational bottlenecks were identified with the help of Mr. Christian Gabuya.

From late March to April 2026, the researchers focused on the Technical Conceptualization and System Requirement Analysis phases to establish the necessary specifications for symbol detection and 3D visualization. Following this, in May 2026, the researchers moved into the Prototyping stage by developing low-fidelity and high-fidelity wireframes using Figma. This involved designing separate interface modules for the Admin and User roles to ensure a structured navigation flow for the AI-driven floor plan analysis and automated costing features. These Figma prototypes served as the visual bridge between the technical requirements and the actual system development, allowing the researchers to refine the interaction logic before final implementation. The chronological progression of these activities, from the early research stages to the interface design phase in May, leading up to the title defense, is documented in the Gantt Chart (see Appendix D).

## Scope and Limitation of the Study

The study developed “VED Electrical Services: AI-Driven Floor Plan Analysis and 3D Visualization System,” a specialized platform designed to automate the initial stages of electrical layouting and material cost estimation. The system aims to provide VED Electrical Services with a digital tool that replaces the traditional, manual process of counting components and measuring wire lengths. A web-based application was created for Electrical Designers to process 2D blueprints into interactive 3D environments, while a management module was developed for Project Engineers to oversee material costs and technical accuracy.

The Electrical Designer manages the core functionalities of the system, which includes uploading digital floor plans in JPEG, PNG, or PDF format. Through its AI features, the system analyzes the blueprint on a per-room basis to ensure detailed accuracy for every section of a building. It automatically detects and counts the standard symbols used by the company, such as lighting fixtures, power outlets, switches, and data ports. Once a room is processed, the system transforms the 2D layout into an interactive 3D model, allowing the designer to manually plot additional wiring paths, conduits, and other fixtures in real-time. The Admin is responsible for maintaining the SQL pricing database, ensuring that the material costs used for the automated estimation are based on the official price list provided by the company.

The study identified specific operational boundaries. The system is primarily focused on residential floor plans and commercial structures, such as houses or office spaces. To ensure high detection accuracy, the system is trained strictly on the standard legends and symbols used by VED Electrical Services; hence, non-standard or custom-made architectural icons from other firms are excluded from automatic recognition. To protect the integrity of the project, the system does not modify the original uploaded 2D blueprint—it only uses it as a reference for the 3D generation and layout overlay.

The study also highlighted the need for professional and legal validation. The system serves as a Planning and Estimation Tool only and does not replace the final technical plans required for building permits. In compliance with the Philippine Electrical Code (PEC), all 3D-generated layouts and cost estimates must still be reviewed, validated, and signed by a Licensed Professional Engineer before any actual site installation or official permit application.

However, the system has certain limitations. It does not support offline mode because it requires an active internet connection to load 3D rendering libraries. The system’s accuracy is highly dependent on the quality of the upload; therefore, hand-drawn sketches or low-resolution images are excluded as they may lead to detection errors. To ensure smooth 3D performance, the minimum hardware requirement is a computer with at least 8 GB of RAM and a modern web browser with WebGL support. Lastly, the cost estimation uses a fixed database provided by the company and does not reflect real-time market price fluctuations unless manually updated by the administrator.

## Definition of Terms

For the purpose of clarity and consistency, the following terms are defined according to their usage in this study.

### 2D Visualization

Refers to the digital representation and rendering of electrical schematics and spatial layouts in a two-dimensional plane. In this study, it is utilized to enable real-time user interaction, including the placement of electrical components and visualization of wiring trajectories.

### 3D Visualization

Refers to the three-dimensional graphical representation of spatial layouts that simulate depth, perspective, and physical structure. In this study, it is applied to generate interactive models of floor plans, allowing users to examine electrical layouts within a realistic spatial environment.

### Automated Cost Estimation

The technique uses linear footage and observed material amounts compared to a price database to forecast the total project costs.

### Computer Vision (CV)

Refers to the field of study that enables machines to interpret and process visual data from images. In this research, it is specifically utilized for detecting and recognizing structural elements such as walls, doors, and electrical symbols from high-resolution floor plan inputs.

### Conduit

A tube or pipe used in the system to route and protect electrical wiring is called a spatial element that requires precise length and cost estimates.

### Design Thinking Methodology

An iterative, user-centric process called Empathize, Define, Ideate, Prototype, and Test ensures that the solution addresses the particular operational challenges faced by electrical designers.

### Floor Plan Analysis

Refers to the primary dataset used for spatial analysis, consisting of high-resolution digital blueprints or scanned images of residential structures. In this study, it serves as the foundational input for symbol detection and layout generation processes.

### Input-Process-Output (IPO) Model

Refers to a systems framework that describes the transformation of inputs into outputs through a defined process. In this study, it represents the functional architecture that converts raw floor plan data into automated electrical layouts, estimations, and visual representations.

### ISO 25010 Standard

This study used an international standard for software quality evaluation to evaluate the system's usability, performance efficiency, and functional suitability.

### Layout Generation

Refers to the computational process of transforming detected architectural elements into structured visual outputs. In this study, it involves the simultaneous generation of 2D electrical schematics and interactive 3D spatial models.

### Linear Footage

Refers to the total measured length of electrical wiring and conduits required for installation. In this study, it is calculated based on the system’s geometric analysis of routing paths within the generated layout.

### OpenCV (Open Source Computer Vision Library)

An open-source library of programming functions intended for real-time computer vision is used by the system's image processing and symbol detection modules.

### Roughing-ins

The system attempts to automate the estimation of these materials during the initial phase of electrical installation, which involves placing conduits and boxes before walls are closed.

### Spatial Routing Algorithm

Refers to a computational method used to determine efficient paths within a spatial environment. In this study, it is employed to identify optimal wiring routes by minimizing distance and avoiding structural constraints within the floor plan.

### Symbol Detection and Classification

Refers to the process of identifying visual elements within an image and assigning them to predefined categories. In this study, it involves detecting architectural and electrical symbols and labeling them (e.g., outlets, switches, lighting fixtures) using a trained machine learning model.

### System Output

Refers to the final results generated by the system after processing the input data. In this study, it includes the produced electrical layouts, calculated material estimates (such as linear footage), and corresponding cost analysis reports.

### Three.js

Refers to a JavaScript-based rendering framework utilized for the generation of 3D computer graphics. In this research, it is employed as the front-end visualization platform to render the structural and electrical components of a floor plan, facilitating user interaction with the spatial environment without the need for external plugins or specialized hardware.

### WebGL (Web Graphics Library)

Any compatible web browser may generate high-performance interactive 2D and 3D graphics using a JavaScript API without the need for any plug-ins.
