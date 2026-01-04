# Audit Report: `backend/services/ai_router.py`

## Executive Summary

This audit reviews `ai_router.py` for best practices, focusing on context engineering principles from LangChain documentation. The code is functional but has several areas for improvement regarding context management, error handling, and performance.

---

## Critical Issues

### 1. **Syntax Error (Line 21)**
```python
except ImportError:
    # Если прямой импорт не работает, используем общий Exception
```
**Issue**: Missing `except` clause continuation - the code appears incomplete.

**Impact**: This will cause a syntax error at runtime.

**Recommendation**: Complete the exception handling block.

---

### 2. **Duplicate Exception Handlers (Lines 322-343)**
```python
except Exception as e:
    # First handler (line 322)
    ...
except Exception as e:
    # Second handler (line 341) - UNREACHABLE!
```
**Issue**: Two `except Exception` blocks - the second is unreachable.

**Impact**: Dead code, potential confusion.

**Recommendation**: Remove duplicate handler or consolidate error handling logic.

---

## Context Engineering Issues

### 3. **No Context Truncation/Limiting**

**Current State**: All messages from `request.context` are deserialized without any limits.

**Problem**: 
- Context can grow unbounded, leading to:
  - Token limit exceeded errors
  - Increased latency
  - Higher API costs
  - Memory issues

**Best Practice** (from LangChain docs):
- Implement **context compression** strategy
- Use **SummarizationMiddleware** for long conversations
- Limit context window (e.g., last N messages or token count)

**Recommendation**:
```python
# Add context limiting before deserialization
MAX_CONTEXT_MESSAGES = 50  # or calculate based on tokens
if request.context and len(request.context) > MAX_CONTEXT_MESSAGES:
    # Keep most recent messages
    request.context = request.context[-MAX_CONTEXT_MESSAGES:]
    logger.info(f"Context truncated to {MAX_CONTEXT_MESSAGES} messages")
```

### 4. **No Token Counting**

**Issue**: No validation of token count before sending to agent.

**Impact**: Risk of exceeding model's context window, causing failures.

**Recommendation**: 
- Use LangChain's token counting utilities
- Validate total tokens (system prompt + messages + KB) before agent invocation
- Implement proactive truncation if approaching limits

### 5. **Missing Context Compression Strategy**

**Current State**: Tool messages are preserved but never compressed.

**Best Practice**: According to LangChain documentation:
- **Compress Context**: Retain only essential tokens by summarizing conversations
- Use `SummarizationMiddleware` for automatic compression
- Compress tool outputs for long agent trajectories

**Recommendation**: 
- Implement summarization for old messages (beyond last N)
- Compress tool message results if they're too verbose
- Consider using LangChain's built-in `SummarizationMiddleware`

### 6. **No Message Validation**

**Issue**: Deserialized messages are not validated for:
- Content length
- Malformed structure
- Invalid tool_call_ids
- Missing required fields

**Security Risk**: Malformed messages could cause agent failures or unexpected behavior.

**Recommendation**:
```python
def validate_message(msg_dict: dict) -> bool:
    """Validate message structure before deserialization."""
    required_fields = {"type", "content"}
    if not required_fields.issubset(msg_dict.keys()):
        return False
    if len(msg_dict.get("content", "")) > MAX_MESSAGE_LENGTH:
        return False
    return True
```

---

## Code Quality Issues

### 7. **Custom Serialization Instead of LangChain Utilities**

**Current State**: Custom `serialize_messages()` and `deserialize_messages()` functions.

**Issue**: LangChain provides built-in message serialization methods that handle edge cases better.

**Best Practice**: Use LangChain's native serialization:
```python
from langchain_core.messages import messages_to_dict, messages_from_dict

# Instead of custom serialize_messages()
serialized = messages_to_dict(messages)

# Instead of custom deserialize_messages()
messages = messages_from_dict(context)
```

**Benefits**:
- Handles all message types correctly
- Preserves metadata (timestamps, IDs)
- Better error handling
- Future-proof against LangChain updates

### 8. **Incomplete Tool Call Serialization**

**Current State**: Tool calls are serialized but may miss important fields.

**Issue**: Tool calls in LangChain can have additional fields like:
- `type` (function/tool)
- `kwargs` (additional arguments)
- Message-level metadata

**Recommendation**: Use LangChain's built-in serialization which handles all fields correctly.

### 9. **Missing Message Metadata Preservation**

**Issue**: Custom serialization doesn't preserve:
- Message IDs
- Timestamps
- Additional metadata (e.g., `additional_kwargs`)

**Impact**: Loss of important context that could be useful for debugging or advanced features.

---

## Performance Issues

### 10. **No Context Window Management**

**Issue**: All messages are sent to agent without checking if they fit in context window.

**Impact**: 
- Unnecessary API calls that will fail
- Wasted tokens
- Poor user experience

**Recommendation**: 
- Calculate approximate token count before agent invocation
- Implement sliding window or summarization
- Return error early if context is too large

### 11. **Inefficient Fallback Logic**

**Current State**: Fallback deserialization iterates through all messages again.

**Issue**: If deserialization fails, the fallback re-processes the same data.

**Recommendation**: 
- Validate context format before attempting deserialization
- Use a single, robust deserialization path
- Log format issues for monitoring

---

## Security Concerns

### 12. **No Input Sanitization**

**Issue**: User message and context content are not sanitized before processing.

**Risk**: 
- Prompt injection attacks
- Context poisoning
- Malicious content in messages

**Recommendation**:
```python
def sanitize_message_content(content: str) -> str:
    """Sanitize message content to prevent injection attacks."""
    # Remove potential prompt injection patterns
    # Limit content length
    # Validate encoding
    return sanitized_content
```

### 13. **Context Injection Risk**

**Issue**: Context from client is trusted without validation.

**Risk**: Malicious client could inject:
- Fake tool calls
- Corrupted message structure
- Excessive data to cause DoS

**Recommendation**: 
- Validate context structure strictly
- Limit context size
- Sanitize all content
- Consider server-side context storage instead of client-provided

---

## Best Practices Violations

### 14. **Not Using LangChain's Message Utilities**

**Best Practice**: LangChain provides `messages_to_dict()` and `messages_from_dict()` which:
- Handle all message types correctly
- Preserve metadata
- Are tested and maintained

**Current**: Custom implementation that may miss edge cases.

### 15. **No Context Isolation Strategy**

**Best Practice**: According to LangChain docs, context should be:
- **Isolated**: Split context across separate processing units
- **Selected**: Retrieve only relevant information
- **Compressed**: Summarize when needed

**Current**: All context is sent without filtering or compression.

### 16. **Missing Error Context in Logs**

**Issue**: Error logging doesn't include context size or structure information.

**Recommendation**: 
```python
logger.error(
    f"Failed to deserialize context: {e}. "
    f"Context size: {len(request.context)}, "
    f"First message: {request.context[0] if request.context else None}"
)
```

---

## Recommendations Priority

### High Priority (Fix Immediately)

1. **Fix syntax error** (line 21)
2. **Remove duplicate exception handler** (line 341)
3. **Add context truncation** to prevent unbounded growth
4. **Implement input validation** for security

### Medium Priority (Improve Soon)

5. **Replace custom serialization** with LangChain's `messages_to_dict/messages_from_dict`
6. **Add token counting** before agent invocation
7. **Implement context compression** for long conversations
8. **Add message validation** before deserialization

### Low Priority (Nice to Have)

9. **Add context window management** with proactive truncation
10. **Implement SummarizationMiddleware** for automatic compression
11. **Add comprehensive error context** in logs
12. **Consider server-side context storage** instead of client-provided

---

## Code Examples for Improvements

### Example 1: Using LangChain Serialization
```python
from langchain_core.messages import messages_to_dict, messages_from_dict

# Serialization
def serialize_messages(messages: List[BaseMessage]) -> List[dict]:
    """Use LangChain's built-in serialization."""
    return messages_to_dict(messages)

# Deserialization
def deserialize_messages(context: List[dict]) -> List[BaseMessage]:
    """Use LangChain's built-in deserialization."""
    try:
        return messages_from_dict(context)
    except Exception as e:
        logger.error(f"Failed to deserialize: {e}")
        raise
```

### Example 2: Context Truncation
```python
MAX_CONTEXT_MESSAGES = 50
MAX_CONTEXT_TOKENS = 8000  # Approximate

def truncate_context(context: List[dict]) -> List[dict]:
    """Truncate context to prevent unbounded growth."""
    if not context:
        return context
    
    # Limit by message count
    if len(context) > MAX_CONTEXT_MESSAGES:
        logger.info(f"Truncating context from {len(context)} to {MAX_CONTEXT_MESSAGES} messages")
        return context[-MAX_CONTEXT_MESSAGES:]
    
    return context
```

### Example 3: Token Counting
```python
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

def estimate_tokens(messages: List[BaseMessage], system_prompt: str) -> int:
    """Estimate token count for messages."""
    # Rough estimation: 1 token ≈ 4 characters
    total_chars = len(system_prompt)
    for msg in messages:
        if hasattr(msg, 'content'):
            total_chars += len(str(msg.content))
    return total_chars // 4
```

---

## Conclusion

The current implementation is functional but needs improvements in:
- **Context management**: Add truncation, compression, and validation
- **Error handling**: Fix syntax errors and duplicate handlers
- **Security**: Add input sanitization and validation
- **Best practices**: Use LangChain's built-in utilities

Following these recommendations will improve reliability, security, and performance while aligning with LangChain's context engineering best practices.

