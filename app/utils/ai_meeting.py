import anthropic
import json
from flask import current_app

def extract_tasks_from_notes(notes_text, group_members, group_name):
    # Build member list string
    member_strings = []
    for m in group_members:
        member_strings.append(f"- {m['username']} (id: {m['user_id']})")
    member_list_string = "\\n".join(member_strings)

    try:
        client = anthropic.Anthropic(
            api_key=current_app.config['ANTHROPIC_API_KEY']
        )
        
        system_message = (
            "You are a project management assistant that "
            "analyzes meeting notes and extracts action items. "
            "You always respond with valid JSON only. "
            "No explanation, no markdown formatting, "
            "no code blocks. Just raw JSON."
        )
        
        user_message = f"""Analyze these meeting notes from a team
called '{group_name}' and extract all action
items and tasks.

Team members available for assignment:
{member_list_string}

Meeting notes:
{notes_text}

Return a JSON object with this exact structure:
{{
  "summary": "2-3 sentence summary of meeting",
  "key_decisions": [
    "decision 1",
    "decision 2"
  ],
  "tasks": [
    {{
      "title": "Short actionable task title starting with a verb",
      "description": "More detail if mentioned",
      "suggested_assignee_id": 123 or null,
      "suggested_assignee_name": "username" or null,
      "suggested_deadline_days": 7 or null,
      "priority": "high" or "medium" or "low",
      "reason": "Why this was extracted as a task"
    }}
  ],
  "total_tasks_found": 3
}}

Rules:
- Only extract clear action items not discussions
- If a name is mentioned with an action assign them
- Match names to the team member list provided
- Convert deadlines to days from today:
    'by Friday' = 5, 'next week' = 7,
    'tomorrow' = 1, 'end of month' = 30
- Task titles must start with a verb:
    Good: 'Build login page', 'Review designs'
    Bad: 'Login page', 'The design'
- Maximum 15 tasks
- If no clear tasks return empty tasks array"""

        response = client.messages.create(
            model='claude-opus-4-20250514',
            max_tokens=2000,
            system=system_message,
            messages=[{
                "role": "user",
                "content": user_message
            }]
        )
        
        text = response.content[0].text.strip()
        result = json.loads(text)
        
        # Validate result keys
        defaults = {
            "summary": "No summary provided",
            "key_decisions": [],
            "tasks": [],
            "total_tasks_found": 0
        }
        for k, v in defaults.items():
            if k not in result:
                result[k] = v
                
        return result
        
    except json.JSONDecodeError:
        return {
            "summary": "Could not analyze notes",
            "key_decisions": [],
            "tasks": [],
            "total_tasks_found": 0,
            "error": "AI response was not valid JSON. Please try again."
        }
    except Exception as e:
        error_msg = str(e).lower()
        if "credit balance is too low" in error_msg or '400' in error_msg or '429' in error_msg:
            return {
                "summary": "Mock Analysis: This is a simulated summary because the Anthropic API key provided has insufficient credits. The system has automatically generated these mock tasks based on the example notes so you can still try out the application workflow!",
                "key_decisions": [
                    "Use PostgreSQL instead of MySQL",
                    "Project report will be submitted in PDF format"
                ],
                "tasks": [
                    {
                        "title": "Review project requirements document",
                        "description": "Review the document and come prepared with questions.",
                        "suggested_assignee_id": None,
                        "suggested_assignee_name": None,
                        "suggested_deadline_days": 3,
                        "priority": "medium",
                        "reason": "Mentioned that everyone needs to do this."
                    },
                    {
                        "title": "Add proper error handling to all API endpoints",
                        "description": "Needs to be completed before the next review.",
                        "suggested_assignee_id": None,
                        "suggested_assignee_name": "Rahul",
                        "suggested_deadline_days": 5,
                        "priority": "high",
                        "reason": "Rahul was specifically assigned to this."
                    }
                ],
                "total_tasks_found": 2
            }
            
        return {
            "summary": "Analysis failed",
            "key_decisions": [],
            "tasks": [],
            "total_tasks_found": 0,
            "error": f"Error: {str(e)}"
        }
