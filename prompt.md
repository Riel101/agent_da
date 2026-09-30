## Overview
Build an agent that helps users achieve long term agendas by breaking it down into smaller daily agendas.

### User pipeline
The user experience looks something like this;
-user creates account 
-user creates a new agenda, selects a timeframe (in days) to achieve the agenda, selects a channel to receive daily reminders for sub-agendas (WhatsApp or Email), and selects a time (e.g., 8am daily) to receive a daily reminder for the sub-agenda each day
-the agent creates progressive sub-agendas aligned to achieving the main agenda, to be achieved each day within the timeframe, and shows it to the user for edits and/or corrections. Ensure the main agenda is achieved on the last day of the timeframe
-after the user is satisfied with the daily sub-agendas, the agenda is successfully created
-every day within the timeframe, a todo list is created aligned with the sub-agenda for the day, essentially like a breakdown of what the user must do each day to achieve the main agenda within the timeframe
-for every day within the timeframe, the user receives a message to the previously selected reminder channel. The message contains a little motivation and the to-do for the day and titled with the sub-agenda for the day
-the user can go to their dashboard, to edit the to-do list, if they want to remove or add to the list
-the user can come tick items in the to-do list as they complete each task. they earn points for each task completed

### The project stack
Agent -> LangChain
Frontend -> React and Tailwind
Backend -> LangGraph
Hosting -> Render
LLM -> nvidia/nemotron-3-ultra-550b-a55b


### Additions
Ask for any additional information that is required that I might have missed