"""
a11y_engine.py - Deterministic, offline accessibility checker using baseline DOM rules.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class A11yEngine:
    def __init__(self) -> None:
        pass

    def scan_page(self, page: Any) -> Dict[str, Any]:
        """
        Execute JavaScript DOM evaluation in browser page to find accessibility violations.
        """
        if not page:
            raise ValueError("Playwright page object is required for accessibility scan.")

        js_code = """() => {
            const getCssSelector = (el) => {
                if (!el || el.nodeType !== 1) return "";
                if (el.id) return "#" + el.id;
                let path = [];
                let current = el;
                while (current && current.nodeType === 1) {
                    let tagName = current.nodeName.toLowerCase();
                    let index = 1;
                    let sibling = current.previousElementSibling;
                    while (sibling) {
                        if (sibling.nodeName === current.nodeName) {
                            index++;
                        }
                        sibling = sibling.previousElementSibling;
                    }
                    path.unshift(`${tagName}:nth-of-type(${index})`);
                    current = current.parentNode;
                }
                return path.join(" > ");
            };

            const violations = [];
            let passedCount = 0;

            // 1. image missing alt
            const imgs = document.querySelectorAll("img");
            imgs.forEach(img => {
                if (!img.hasAttribute("alt")) {
                    violations.push({
                        rule_id: "image-missing-alt",
                        description: "Image is missing alt attribute",
                        severity: "critical",
                        selector: getCssSelector(img),
                        html: img.outerHTML.substring(0, 500)
                    });
                } else {
                    passedCount++;
                }
            });

            // 2. input missing label
            const inputs = document.querySelectorAll("input, select, textarea");
            inputs.forEach(input => {
                const type = input.getAttribute("type");
                if (type && ["hidden", "submit", "button", "image", "reset"].includes(type.toLowerCase())) {
                    return;
                }
                let hasLabel = false;
                if (input.closest("label")) {
                    hasLabel = true;
                }
                const id = input.id;
                if (id && document.querySelector(`label[for="${id}"]`)) {
                    hasLabel = true;
                }
                if (input.getAttribute("aria-label") || input.getAttribute("aria-labelledby") || input.getAttribute("title") || input.getAttribute("placeholder")) {
                    hasLabel = true;
                }
                if (!hasLabel) {
                    violations.push({
                        rule_id: "input-missing-label",
                        description: "Form input lacks associated label, title, or aria-label.",
                        severity: "serious",
                        selector: getCssSelector(input),
                        html: input.outerHTML.substring(0, 500)
                    });
                } else {
                    passedCount++;
                }
            });

            // 3. button missing accessible name
            const buttons = document.querySelectorAll("button");
            buttons.forEach(btn => {
                const text = (btn.innerText || btn.textContent || "").trim();
                const ariaLabel = btn.getAttribute("aria-label");
                const ariaLabelledBy = btn.getAttribute("aria-labelledby");
                const title = btn.getAttribute("title");
                if (!text && !ariaLabel && !ariaLabelledBy && !title) {
                    violations.push({
                        rule_id: "button-missing-name",
                        description: "Button lacks accessible text, aria-label, or title.",
                        severity: "critical",
                        selector: getCssSelector(btn),
                        html: btn.outerHTML.substring(0, 500)
                    });
                } else {
                    passedCount++;
                }
            });

            // 4. link missing accessible name
            const links = document.querySelectorAll("a");
            links.forEach(link => {
                const text = (link.innerText || link.textContent || "").trim();
                const ariaLabel = link.getAttribute("aria-label");
                const ariaLabelledBy = link.getAttribute("aria-labelledby");
                const title = link.getAttribute("title");
                if (!link.getAttribute("href") && !text) {
                    return;
                }
                const imgsInLink = link.querySelectorAll("img");
                let hasImgAlt = false;
                imgsInLink.forEach(img => {
                    if (img.getAttribute("alt")) {
                        hasImgAlt = true;
                    }
                });
                if (!text && !ariaLabel && !ariaLabelledBy && !title && !hasImgAlt) {
                    violations.push({
                        rule_id: "link-missing-name",
                        description: "Link lacks accessible text, aria-label, or title.",
                        severity: "serious",
                        selector: getCssSelector(link),
                        html: link.outerHTML.substring(0, 500)
                    });
                } else {
                    passedCount++;
                }
            });

            return {
                violations: violations,
                passed_count: passedCount
            };
        }"""
        res = page.evaluate(js_code)
        violations = res.get("violations", [])
        passed_count = res.get("passed_count", 0)

        # Compute summary
        total_violations = len(violations)
        critical_violations = sum(1 for v in violations if v.get("severity") == "critical")
        serious_violations = sum(1 for v in violations if v.get("severity") == "serious")

        return {
            "total_violations": total_violations,
            "critical_violations": critical_violations,
            "serious_violations": serious_violations,
            "passed_count": passed_count,
            "violations": violations,
        }
