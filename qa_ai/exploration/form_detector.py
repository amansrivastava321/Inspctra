"""
form_detector.py - Detects forms, inputs, and interactive elements in a page.
Identifies text inputs, password fields, selects, checkboxes, submit buttons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class DetectedInput:
    """A single form input field."""
    input_type: str                # "text", "password", "email", "number", "textarea", etc.
    name: str = ""
    id: str = ""
    placeholder: str = ""
    label: str = ""
    required: bool = False
    selector: str = ""
    value: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_type": self.input_type,
            "name": self.name,
            "id": self.id,
            "placeholder": self.placeholder,
            "label": self.label,
            "required": self.required,
            "selector": self.selector,
            "value": self.value,
        }


@dataclass
class DetectedSelect:
    """A select/dropdown element."""
    name: str = ""
    id: str = ""
    selector: str = ""
    options: List[str] = field(default_factory=list)
    required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "id": self.id,
            "selector": self.selector,
            "options": self.options,
            "required": self.required,
        }


@dataclass
class DetectedCheckbox:
    """A checkbox or radio button."""
    input_type: str = "checkbox"   # "checkbox" or "radio"
    name: str = ""
    id: str = ""
    value: str = ""
    label: str = ""
    selector: str = ""
    checked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_type": self.input_type,
            "name": self.name,
            "id": self.id,
            "value": self.value,
            "label": self.label,
            "selector": self.selector,
            "checked": self.checked,
        }


@dataclass
class DetectedButton:
    """A submit or action button."""
    button_type: str               # "submit", "button", "reset"
    text: str = ""
    id: str = ""
    name: str = ""
    selector: str = ""
    disabled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "button_type": self.button_type,
            "text": self.text,
            "id": self.id,
            "name": self.name,
            "selector": self.selector,
            "disabled": self.disabled,
        }


@dataclass
class DetectedForm:
    """A complete form with its inputs, selects, checkboxes, and buttons."""
    form_id: str = ""
    form_name: str = ""
    action: str = ""
    method: str = "GET"
    selector: str = ""
    inputs: List[DetectedInput] = field(default_factory=list)
    selects: List[DetectedSelect] = field(default_factory=list)
    checkboxes: List[DetectedCheckbox] = field(default_factory=list)
    buttons: List[DetectedButton] = field(default_factory=list)
    has_password: bool = False
    has_file_upload: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "form_id": self.form_id,
            "form_name": self.form_name,
            "action": self.action,
            "method": self.method,
            "selector": self.selector,
            "inputs": [i.to_dict() for i in self.inputs],
            "selects": [s.to_dict() for s in self.selects],
            "checkboxes": [c.to_dict() for c in self.checkboxes],
            "buttons": [b.to_dict() for b in self.buttons],
            "has_password": self.has_password,
            "has_file_upload": self.has_file_upload,
            "total_fields": len(self.inputs) + len(self.selects) + len(self.checkboxes),
        }


class FormDetector:
    """
    Detects forms and their constituent elements on a page.

    Works with Playwright Page objects to extract form structure.
    Also provides static analysis helpers for HTML content.
    """

    # JavaScript to extract form data from the page
    EXTRACT_FORMS_JS = """
    () => {
        const forms = [];
        const formElements = document.querySelectorAll('form');
        formElements.forEach((form, fi) => {
            const formData = {
                form_id: form.id || '',
                form_name: form.name || '',
                action: form.action || '',
                method: (form.method || 'GET').toUpperCase(),
                selector: form.id ? `#${form.id}` : `form:nth-of-type(${fi + 1})`,
                inputs: [],
                selects: [],
                checkboxes: [],
                buttons: [],
                has_password: false,
                has_file_upload: false,
            };

            // Inputs
            form.querySelectorAll('input').forEach(input => {
                const type = (input.type || 'text').toLowerCase();
                if (type === 'hidden') return;

                const label = input.closest('label')?.textContent?.trim() ||
                    (input.id && document.querySelector(`label[for="${input.id}"]`)?.textContent?.trim()) || '';

                if (type === 'checkbox' || type === 'radio') {
                    formData.checkboxes.push({
                        input_type: type,
                        name: input.name || '',
                        id: input.id || '',
                        value: input.value || '',
                        label: label,
                        selector: input.id ? `#${input.id}` : input.name ? `input[name="${input.name}"]` : '',
                        checked: input.checked,
                    });
                } else if (type === 'file') {
                    formData.has_file_upload = true;
                    formData.inputs.push({
                        input_type: type,
                        name: input.name || '',
                        id: input.id || '',
                        placeholder: input.placeholder || '',
                        label: label,
                        required: input.required,
                        selector: input.id ? `#${input.id}` : '',
                        value: '',
                    });
                } else {
                    if (type === 'password') formData.has_password = true;
                    formData.inputs.push({
                        input_type: type,
                        name: input.name || '',
                        id: input.id || '',
                        placeholder: input.placeholder || '',
                        label: label,
                        required: input.required,
                        selector: input.id ? `#${input.id}` : '',
                        value: input.value || '',
                    });
                }
            });

            // Textareas
            form.querySelectorAll('textarea').forEach(ta => {
                const label = ta.closest('label')?.textContent?.trim() ||
                    (ta.id && document.querySelector(`label[for="${ta.id}"]`)?.textContent?.trim()) || '';
                formData.inputs.push({
                    input_type: 'textarea',
                    name: ta.name || '',
                    id: ta.id || '',
                    placeholder: ta.placeholder || '',
                    label: label,
                    required: ta.required,
                    selector: ta.id ? `#${ta.id}` : '',
                    value: '',
                });
            });

            // Selects
            form.querySelectorAll('select').forEach(sel => {
                const options = Array.from(sel.options).map(o => o.textContent?.trim() || o.value);
                const label = sel.closest('label')?.textContent?.trim() ||
                    (sel.id && document.querySelector(`label[for="${sel.id}"]`)?.textContent?.trim()) || '';
                formData.selects.push({
                    name: sel.name || '',
                    id: sel.id || '',
                    selector: sel.id ? `#${sel.id}` : '',
                    options: options,
                    required: sel.required,
                });
            });

            // Buttons
            form.querySelectorAll('button, input[type="submit"], input[type="button"], input[type="reset"]').forEach(btn => {
                const type = btn.type || (btn.tagName === 'BUTTON' ? 'submit' : 'button');
                const text = btn.textContent?.trim() || btn.value || '';
                formData.buttons.push({
                    button_type: type,
                    text: text,
                    id: btn.id || '',
                    name: btn.name || '',
                    selector: btn.id ? `#${btn.id}` : '',
                    disabled: btn.disabled,
                });
            });

            forms.push(formData);
        });
        return forms;
    }
    """

    def detect_forms(self, page: Any) -> List[DetectedForm]:
        """
        Detect all forms on a Playwright Page object.

        Args:
            page: A Playwright Page instance

        Returns:
            List of DetectedForm objects
        """
        try:
            raw_forms = page.evaluate(self.EXTRACT_FORMS_JS)
            return [self._parse_form(f) for f in raw_forms]
        except Exception as e:
            logger.warning(f"Form detection failed: {e}")
            return []

    def detect_forms_from_html(self, html: str) -> List[DetectedForm]:
        """
        Detect forms from raw HTML string (no browser needed).
        Uses regex-based parsing as a fallback.
        """
        import re
        forms = []
        # Match the opening <form ...> tag, then capture everything until </form>
        form_open_pattern = re.compile(
            r'<form\b([^>]*)>',
            re.IGNORECASE,
        )
        form_close_pattern = re.compile(
            r'</form>',
            re.IGNORECASE,
        )
        input_pattern = re.compile(
            r'<input\b[^>]*>',
            re.IGNORECASE,
        )
        textarea_pattern = re.compile(
            r'<textarea\b[^>]*>.*?</textarea>',
            re.DOTALL | re.IGNORECASE,
        )
        select_pattern = re.compile(
            r'<select\b[^>]*>.*?</select>',
            re.DOTALL | re.IGNORECASE,
        )
        button_pattern = re.compile(
            r'<(?:button\b[^>]*>.*?</button>|input\s+type=["\'](?:submit|button|reset)["\'][^>]*>)',
            re.IGNORECASE,
        )

        # Find all form open tags and their content
        open_matches = list(form_open_pattern.finditer(html))
        close_matches = list(form_close_pattern.finditer(html))

        for i, open_match in enumerate(open_matches):
            # Find the corresponding closing tag
            if i < len(close_matches):
                form_content = html[open_match.end():close_matches[i].start()]
            else:
                form_content = html[open_match.end():]

            attrs = self._parse_tag_attrs(open_match.group(1))
            form = DetectedForm(
                form_id=attrs.get("id", ""),
                form_name=attrs.get("name", ""),
                action=attrs.get("action", ""),
                method=attrs.get("method", "GET").upper(),
                selector=f"#{attrs['id']}" if attrs.get("id") else f"form:nth-of-type({i + 1})",
            )

            for inp_match in input_pattern.finditer(form_content):
                inp_attrs = self._parse_tag_attrs(inp_match.group(0))
                inp_type = inp_attrs.get("type", "text").lower()
                if inp_type == "hidden":
                    continue
                if inp_type in ("checkbox", "radio"):
                    form.checkboxes.append(DetectedCheckbox(
                        input_type=inp_type,
                        name=inp_attrs.get("name", ""),
                        id=inp_attrs.get("id", ""),
                        value=inp_attrs.get("value", ""),
                        selector=f"#{inp_attrs['id']}" if inp_attrs.get("id") else "",
                    ))
                elif inp_type == "file":
                    form.has_file_upload = True
                    form.inputs.append(DetectedInput(
                        input_type=inp_type,
                        name=inp_attrs.get("name", ""),
                        id=inp_attrs.get("id", ""),
                        placeholder=inp_attrs.get("placeholder", ""),
                        required="required" in inp_attrs,
                        selector=f"#{inp_attrs['id']}" if inp_attrs.get("id") else "",
                    ))
                else:
                    if inp_type == "password":
                        form.has_password = True
                    form.inputs.append(DetectedInput(
                        input_type=inp_type,
                        name=inp_attrs.get("name", ""),
                        id=inp_attrs.get("id", ""),
                        placeholder=inp_attrs.get("placeholder", ""),
                        required="required" in inp_attrs,
                        selector=f"#{inp_attrs['id']}" if inp_attrs.get("id") else "",
                    ))

            # Textareas
            for ta_match in textarea_pattern.finditer(form_content):
                ta_attrs = self._parse_tag_attrs(ta_match.group(0))
                form.inputs.append(DetectedInput(
                    input_type="textarea",
                    name=ta_attrs.get("name", ""),
                    id=ta_attrs.get("id", ""),
                    placeholder=ta_attrs.get("placeholder", ""),
                    required="required" in ta_attrs,
                    selector=f"#{ta_attrs['id']}" if ta_attrs.get("id") else "",
                ))

            for sel_match in select_pattern.finditer(form_content):
                sel_attrs = self._parse_tag_attrs(sel_match.group(0))
                form.selects.append(DetectedSelect(
                    name=sel_attrs.get("name", ""),
                    id=sel_attrs.get("id", ""),
                    selector=f"#{sel_attrs['id']}" if sel_attrs.get("id") else "",
                ))

            for btn_match in button_pattern.finditer(form_content):
                btn_html = btn_match.group(0)
                btn_attrs = self._parse_tag_attrs(btn_html)
                btn_type = btn_attrs.get("type", "submit").lower()
                # Extract text from <button>...</button> or value from <input ...>
                text = btn_attrs.get("value", "")
                if not text:
                    import re as re_mod
                    text_match = re_mod.search(r'>([^<]+)<', btn_html)
                    if text_match:
                        text = text_match.group(1).strip()
                form.buttons.append(DetectedButton(
                    button_type=btn_type,
                    text=text,
                    id=btn_attrs.get("id", ""),
                    name=btn_attrs.get("name", ""),
                    selector=f"#{btn_attrs['id']}" if btn_attrs.get("id") else "",
                ))

            forms.append(form)

        return forms

    def _parse_form(self, raw: Dict[str, Any]) -> DetectedForm:
        """Parse raw form data from JavaScript into DetectedForm."""
        return DetectedForm(
            form_id=raw.get("form_id", ""),
            form_name=raw.get("form_name", ""),
            action=raw.get("action", ""),
            method=raw.get("method", "GET"),
            selector=raw.get("selector", ""),
            inputs=[DetectedInput(**inp) for inp in raw.get("inputs", [])],
            selects=[DetectedSelect(**sel) for sel in raw.get("selects", [])],
            checkboxes=[DetectedCheckbox(**cb) for cb in raw.get("checkboxes", [])],
            buttons=[DetectedButton(**btn) for btn in raw.get("buttons", [])],
            has_password=raw.get("has_password", False),
            has_file_upload=raw.get("has_file_upload", False),
        )

    @staticmethod
    def _parse_tag_attrs(tag_html: str) -> Dict[str, str]:
        """Parse attributes from an HTML tag string."""
        import re
        attrs = {}
        attr_pattern = re.compile(r'(\w[\w-]*)\s*=\s*["\']([^"\']*)["\']')
        for m in attr_pattern.finditer(tag_html):
            attrs[m.group(1).lower()] = m.group(2)
        # Also capture boolean attributes like 'required'
        bool_pattern = re.compile(r'\b(required|disabled|checked|readonly)\b', re.IGNORECASE)
        for m in bool_pattern.finditer(tag_html):
            attrs[m.group(1).lower()] = "true"
        return attrs
