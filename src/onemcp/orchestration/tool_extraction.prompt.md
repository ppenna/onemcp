# Tool Type Identification Prompt

Given the following user request, identify the types of tools or capabilities that would be required to accomplish the task. List the tool types in a concise, comma-separated format. Suggest general categories of tools (e.g., "web search", "file system access", "data extraction", "optimization", "constraint satisfaction", "math computation", etc.). Assume the algorithms and code already exists for these tools.

Also provide a brief context for each tool type. e.g., for "data extraction" perhaps "csv", "sqlite", "pdf to markdown", etc.

Some additional context might help in identifying the tool types:
"""
{context}
"""

**Only identify tools for the following user request**:
"""
{user_prompt}
"""

Tool types needed:
```json
[
  {{
    "type": string, 
    "context": string
  }}
]
```
