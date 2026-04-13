# UI Components Quick Start Guide

## Overview

The RAD-ML frontend includes enhanced UI components designed for excellent user experience and clean interactions.

---

## 1. Toast Notifications

### Purpose
Display temporary notifications for user feedback (success, error, warning, info).

### Usage

```javascript
import { useToast } from './components/Toast'

export function MyComponent() {
  const { success, error, warning, info } = useToast()

  const handleSubmit = async () => {
    try {
      await submitData()
      success("Data submitted successfully!")
    } catch (err) {
      error("Failed to submit data: " + err.message)
    }
  }

  return (
    <button onClick={handleSubmit}>Submit</button>
  )
}
```

### Toast Types

```javascript
const { toast } = useToast()

// Success - Green notification
toast.success("Operation completed!", 3000)

// Error - Red notification  
toast.error("Something went wrong!", 3000)

// Warning - Orange notification
toast.warning("Please review this!", 3000)

// Info - Blue notification
toast.info("Just so you know...", 3000)

// Custom duration (in milliseconds, 0 = no auto-dismiss)
toast.success("Long message", 5000)
```

### Toast Props
- **message** (string) - Notification text
- **type** (string) - 'success' | 'error' | 'warning' | 'info'
- **duration** (number) - Auto-dismiss time in ms (default: 3000)

---

## 2. InputField Component

### Purpose
Enhanced text input with validation, visual feedback, and strength indicators.

### Usage

```javascript
import { InputField } from './components/InputField'

export function RegistrationForm() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  // Username validation
  const validateUsername = (value) => {
    if (value.length < 3) {
      return { error: "Minimum 3 characters" }
    }
    if (value.length > 50) {
      return { error: "Maximum 50 characters" }
    }
    if (!/^[a-zA-Z0-9_]+$/.test(value)) {
      return { error: "Only letters, numbers, and underscore allowed" }
    }
    return { success: true }
  }

  // Password validation
  const validatePassword = (value) => {
    if (value.length < 8) {
      return { error: "Minimum 8 characters" }
    }
    if (!/[A-Z]/.test(value)) {
      return { error: "Must include uppercase letter" }
    }
    if (!/[0-9]/.test(value)) {
      return { error: "Must include number" }
    }
    return { success: true }
  }

  return (
    <div>
      <InputField
        label="Username"
        placeholder="Enter username"
        value={username}
        onChange={setUsername}
        validation={validateUsername}
        hint="3-50 characters, alphanumeric"
        maxLength={50}
        required
      />

      <InputField
        label="Password"
        type="password"
        placeholder="Enter password"
        value={password}
        onChange={setPassword}
        validation={validatePassword}
        showStrength={true}
        required
      />
    </div>
  )
}
```

### InputField Props

| Prop | Type | Description |
|------|------|-------------|
| label | string | Input label |
| type | string | 'text', 'password', 'email', 'number' |
| placeholder | string | Placeholder text |
| value | string | Current input value |
| onChange | function | Called on input change |
| onBlur | function | Called on input blur |
| validation | function | Validation function returning {error, success} |
| hint | string | Helper text below input |
| error | string | Error message to display |
| maxLength | number | Maximum characters allowed |
| minLength | number | Minimum characters allowed |
| showStrength | boolean | Show password strength indicator (password only) |
| required | boolean | Mark as required field |
| disabled | boolean | Disable input |
| autoComplete | string | HTML autocomplete attribute |

### Validation Function Return

```javascript
// No error, success
{ success: true }

// Error state
{ error: "Error message here" }

// No validation yet
{ }
```

---

## 3. CSS Classes & Utilities

### Button Classes

```html
<!-- Primary Button -->
<button class="btn-primary">Click Me</button>

<!-- Secondary Button -->
<button class="btn-secondary">Click Me</button>

<!-- Icon Button -->
<button class="btn-icon">+</button>
```

### Form Classes

```html
<!-- Form Group -->
<div class="form-group">
  <label class="form-label">Field Name</label>
  <input type="text" />
  <div class="form-hint">Helper text</div>
  <div class="form-error">Error message</div>
</div>

<!-- Required Indicator -->
<label class="form-label required">Username</label>
```

### Message Classes

```html
<!-- Success Message -->
<div class="message-box success">Data saved successfully!</div>

<!-- Error Message -->
<div class="message-box error">Something went wrong</div>

<!-- Warning Message -->
<div class="message-box warning">Please review this</div>

<!-- Info Message -->
<div class="message-box info">Informational message</div>
```

### Badge Classes

```html
<!-- Running Badge -->
<span class="badge running">Running</span>

<!-- Success Badge -->
<span class="badge success">Completed</span>

<!-- Error Badge -->
<span class="badge error">Failed</span>

<!-- Warning Badge -->
<span class="badge warning">Warning</span>
```

### Input States

```html
<!-- Error State -->
<input type="text" class="input-error" />

<!-- Success State -->
<input type="text" class="input-success" />

<!-- Loading Spinner -->
<div class="spinner"></div>

<!-- Skeleton Loader -->
<div class="skeleton" style="width: 200px; height: 16px;"></div>
```

---

## 4. Color Variables

Access semantic colors from CSS:

```css
:root {
  /* Status Colors */
  --success: #00e8c8;    /* Cyan - Success */
  --error: #ff5070;      /* Red - Error */
  --warning: #ffb54a;    /* Orange - Warning */
  
  /* Primary */
  --violet: #7c6dfa;     /* Primary brand color */
  --cyan: #00e8c8;       /* Accent - Cyan */
  
  /* Text Colors */
  --text: #e4e4f0;       /* Primary text */
  --text2: #9494bb;      /* Secondary text */
  --text3: #5a5a80;      /* Tertiary text */
  
  /* Backgrounds */
  --bg: #080810;         /* Main background */
  --surface: #10101e;    /* Card background */
  --card: #18182e;       /* Card elevated */
  
  /* Borders */
  --border: #252540;     /* Primary border */
  --border2: #32325a;    /* Secondary border */
}
```

---

## 5. Animations

### Available Animations

```html
<!-- Fade In -->
<div style="animation: fadeIn 0.3s ease;">Content</div>

<!-- Slide Up -->
<div style="animation: slideUp 0.3s ease;">Content</div>

<!-- Slide Down -->
<div style="animation: slideDown 0.3s ease;">Content</div>

<!-- Slide In Left -->
<div style="animation: slideInLeft 0.3s ease;">Content</div>

<!-- Slide In Right -->
<div style="animation: slideInRight 0.3s ease;">Content</div>

<!-- Scale In -->
<div style="animation: scaleIn 0.3s ease;">Content</div>

<!-- Bounce -->
<div style="animation: bounce 0.5s ease;">Content</div>

<!-- Glow -->
<div style="animation: glow 1.5s ease-out infinite;">Content</div>

<!-- Spin (for loaders) -->
<div style="animation: spin 0.8s linear infinite;">Content</div>

<!-- Shake (for errors) -->
<div style="animation: shake 0.4s ease;">Content</div>
```

---

## 6. Form Examples

### Login Form

```javascript
import { InputField } from './components/InputField'
import { useToast } from './components/Toast'

export function LoginForm() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const { success, error } = useToast()

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      })

      if (!response.ok) throw new Error('Login failed')

      success('Logged in successfully!')
      // Redirect to dashboard
    } catch (err) {
      error(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleLogin}>
      <InputField
        label="Username"
        value={username}
        onChange={setUsername}
        placeholder="Your username"
        required
      />

      <InputField
        label="Password"
        type="password"
        value={password}
        onChange={setPassword}
        placeholder="Your password"
        required
      />

      <button 
        type="submit" 
        className="btn-primary"
        disabled={loading}
      >
        {loading ? 'Logging in...' : 'Sign In'}
      </button>
    </form>
  )
}
```

### Registration Form

```javascript
export function RegistrationForm() {
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: ''
  })
  const [loading, setLoading] = useState(false)
  const { success, error } = useToast()

  const validateUsername = (value) => {
    if (value.length < 3) return { error: 'Min 3 chars' }
    if (value.length > 50) return { error: 'Max 50 chars' }
    return { success: true }
  }

  const validateEmail = (value) => {
    if (!value.includes('@')) return { error: 'Invalid email' }
    return { success: true }
  }

  const validatePassword = (value) => {
    if (value.length < 8) return { error: 'Min 8 chars' }
    if (!/[A-Z]/.test(value)) return { error: 'Need uppercase' }
    if (!/[0-9]/.test(value)) return { error: 'Need number' }
    return { success: true }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (form.password !== form.confirmPassword) {
      error('Passwords do not match')
      return
    }

    setLoading(true)

    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: form.username,
          email: form.email,
          password: form.password
        })
      })

      if (!response.ok) throw new Error('Registration failed')

      success('Account created! Please log in.')
      // Redirect to login
    } catch (err) {
      error(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <InputField
        label="Username"
        value={form.username}
        onChange={(v) => setForm({...form, username: v})}
        validation={validateUsername}
        maxLength={50}
        required
      />

      <InputField
        label="Email"
        type="email"
        value={form.email}
        onChange={(v) => setForm({...form, email: v})}
        validation={validateEmail}
        required
      />

      <InputField
        label="Password"
        type="password"
        value={form.password}
        onChange={(v) => setForm({...form, password: v})}
        validation={validatePassword}
        showStrength={true}
        required
      />

      <InputField
        label="Confirm Password"
        type="password"
        value={form.confirmPassword}
        onChange={(v) => setForm({...form, confirmPassword: v})}
        required
      />

      <button 
        type="submit" 
        className="btn-primary"
        disabled={loading}
      >
        {loading ? 'Creating account...' : 'Create Account'}
      </button>
    </form>
  )
}
```

---

## 7. Testing UI Components

### Manual Testing Checklist

- [ ] Click buttons and verify hover effects
- [ ] Type in input fields and watch validation feedback
- [ ] Trigger errors and verify error message display
- [ ] Submit forms and watch loading states
- [ ] Check toast notifications appear and disappear
- [ ] Test on mobile (responsive design)
- [ ] Test keyboard navigation
- [ ] Test with screen reader (accessibility)

### Automated Testing

```bash
# Run UI tests
python test_ui_experience.py

# View results
cat UI_TEST_RESULTS.md
```

---

## 8. Browser DevTools Tips

### Inspect Animations
1. Open DevTools (F12)
2. Go to Animations panel
3. Interact with UI to see animations
4. Slow down animations for debugging

### Check Colors
1. Use color picker tool
2. Verify colors match design
3. Check contrast ratios (WCAG compliance)

### Performance
1. Open Performance tab
2. Record user interaction
3. Check FPS (should be 60fps)
4. Look for forced reflows

---

## 9. Troubleshooting

### Toast Not Appearing
- Ensure component is wrapped in `<ToastProvider>`
- Check browser console for errors
- Verify `useToast()` imported correctly

### Form Validation Not Working
- Check validation function returns correct format
- Verify `touched` state is being tracked
- Check input has `onChange` handler

### Animations Not Smooth
- Check browser supports CSS animations
- Verify no JavaScript blocking rendering
- Use DevTools Performance tab to debug

### Styling Issues
- Clear browser cache (Ctrl+Shift+R)
- Check CSS file is loaded
- Verify CSS variables are defined
- Use browser DevTools to inspect styles

---

## 10. Performance Best Practices

### Component Usage
- Memoize expensive components with `React.memo()`
- Use callback functions instead of inline functions
- Implement lazy loading for large lists
- Debounce validation functions

### CSS
- Use CSS custom properties for theming
- Minimize animations on low-end devices
- Use `transform` and `opacity` for animations (GPU accelerated)
- Avoid animating `width`, `height`, or `position`

### Optimization
```javascript
// Bad - recreates function on every render
<InputField onChange={(v) => setUsername(v)} />

// Good - uses useCallback
const handleUsernameChange = useCallback((v) => {
  setUsername(v)
}, [])
<InputField onChange={handleUsernameChange} />
```

---

## Summary

The RAD-ML UI components provide:
- ✓ Real-time form validation
- ✓ Toast notifications
- ✓ Smooth animations
- ✓ Accessibility features
- ✓ Mobile responsiveness
- ✓ Performance optimized
- ✓ Easy to use API

All components are production-ready and tested!

---

**For more details, see:**
- UI_ENHANCEMENT_REPORT.md - Detailed enhancement report
- UI_TEST_RESULTS.md - Test results
- index.css - CSS utilities and variables
