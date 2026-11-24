import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext, messagebox
import pymupdf
import cv2
import numpy as np
from PIL import Image
import pytesseract
import requests
import os
import glob
import threading
import tempfile
import webbrowser

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class SezginApp:
    def __init__(self, root):
        self.root = root
        self.root.title("متنپرداز")
        self.root.geometry("980x800")


        self.pdf_path = tk.StringVar()
        self.start_page = tk.IntVar(value=1)
        self.end_page = tk.IntVar(value=1)
        self.target_lang = tk.StringVar(value="فارسی")
        self.api_key = tk.StringVar()
        self.split_mode = tk.StringVar(value="double")


        self.ocr_texts = []     
        self.page_images = []
        self.stop_event = threading.Event()
        self.current_phase = None
        self.worker_thread = None
        self.partial_output_dir = "output"
        os.makedirs(self.partial_output_dir, exist_ok=True)

        self._build_ui()

        self.root.protocol("WM_DELETE_WINDOW", self._confirm_exit)
    def _build_ui(self):

        topbar = tk.Frame(self.root, bg="#e0e0e0", pady=4)
        topbar.pack(fill=tk.X, side=tk.TOP)

        self.btn_stop = tk.Button(topbar, text="توقف", command=self._request_stop,
                                   state=tk.DISABLED, width=10, bg="#f0c040")
        self.btn_stop.pack(side=tk.RIGHT, padx=6)

        self.btn_exit = tk.Button(topbar, text="خروج", command=self._confirm_exit,
                                   width=10, bg="#e07070")
        self.btn_exit.pack(side=tk.RIGHT, padx=6)

        self.btn_save = tk.Button(topbar, text="ذخیره متن", command=self._save_text,
                                   state=tk.DISABLED, width=12, bg="#80c080")
        self.btn_save.pack(side=tk.RIGHT, padx=6)

        self.btn_help = tk.Button(topbar, text="راهنما", command=self._show_help,
                                  width=10, bg="#80c0c0")
        self.btn_help.pack(side=tk.RIGHT, padx=6)

        self.lbl_global_status = tk.Label(topbar, text="آماده", fg="#333")
        self.lbl_global_status.pack(side=tk.LEFT, padx=10)


        f1 = tk.LabelFrame(self.root, text="مرحله 1: استخراج، برش صفحات دوتایی و پیش‌پردازش", padx=8, pady=8)
        f1.pack(fill=tk.X, padx=10, pady=5)

        row1 = tk.Frame(f1); row1.pack(fill=tk.X)
        tk.Entry(row1, textvariable=self.pdf_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Button(row1, text="انتخاب PDF", command=self._browse_pdf).pack(side=tk.LEFT)

        row2 = tk.Frame(f1); row2.pack(fill=tk.X, pady=(8, 0))
        tk.Label(row2, text="از صفحه:").pack(side=tk.LEFT)
        tk.Entry(row2, textvariable=self.start_page, width=6).pack(side=tk.LEFT, padx=(4, 16))
        tk.Label(row2, text="تا صفحه:").pack(side=tk.LEFT)
        tk.Entry(row2, textvariable=self.end_page, width=6).pack(side=tk.LEFT, padx=(4, 16))
        tk.Radiobutton(row2, text="دو برگ (چپ و راست)", variable=self.split_mode, value="double").pack(side=tk.LEFT, padx=(0, 8))
        tk.Radiobutton(row2, text="تک برگ", variable=self.split_mode, value="single").pack(side=tk.LEFT, padx=(0, 8))
        self.btn_extract = tk.Button(row2, text="شروع استخراج", command=self._start_extract)
        self.btn_extract.pack(side=tk.LEFT, padx=(0, 8))

        self.pb_extract = ttk.Progressbar(f1, orient=tk.HORIZONTAL, mode='determinate')
        self.pb_extract.pack(fill=tk.X, pady=(8, 0))
        self.lbl_extract = tk.Label(f1, text="آماده")
        self.lbl_extract.pack(anchor=tk.W)


        f2 = tk.LabelFrame(self.root, text="مرحله 2: OCR", padx=8, pady=8)
        f2.pack(fill=tk.X, padx=10, pady=5)

        self.btn_ocr = tk.Button(f2, text="شروع OCR", command=self._start_ocr, state=tk.DISABLED)
        self.btn_ocr.pack(anchor=tk.W)
        self.pb_ocr = ttk.Progressbar(f2, orient=tk.HORIZONTAL, mode='determinate')
        self.pb_ocr.pack(fill=tk.X, pady=(8, 0))
        self.lbl_ocr = tk.Label(f2, text="منتظر مرحله 1")
        self.lbl_ocr.pack(anchor=tk.W)

 
        f3 = tk.LabelFrame(self.root, text="مرحله 3: ترجمه (GapGPT API)", padx=8, pady=8)
        f3.pack(fill=tk.X, padx=10, pady=5)

        row3 = tk.Frame(f3); row3.pack(fill=tk.X)
        tk.Label(row3, text="زبان مقصد:").pack(side=tk.LEFT)
        tk.Entry(row3, textvariable=self.target_lang, width=15).pack(side=tk.LEFT, padx=(4, 16))
        tk.Label(row3, text="API Key:").pack(side=tk.LEFT)
        tk.Entry(row3, textvariable=self.api_key, width=30, show="*").pack(side=tk.LEFT, padx=(4, 0))

        self.btn_translate = tk.Button(f3, text="شروع ترجمه", command=self._start_translate, state=tk.DISABLED)
        self.btn_translate.pack(anchor=tk.W, pady=(6, 0))
        self.pb_translate = ttk.Progressbar(f3, orient=tk.HORIZONTAL, mode='determinate')
        self.pb_translate.pack(fill=tk.X, pady=(8, 0))
        self.lbl_translate = tk.Label(f3, text="منتظر مرحله 2")
        self.lbl_translate.pack(anchor=tk.W)


        f4 = tk.LabelFrame(self.root, text="خروجی متن", padx=8, pady=8)
        f4.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.output = scrolledtext.ScrolledText(f4, wrap=tk.WORD, font=("Tahoma", 10))
        self.output.pack(fill=tk.BOTH, expand=True)

    def _browse_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if path:
            self.pdf_path.set(path)

    def _show_help(self):
        help_text = (
    "این نرم افزار توسط مصطفی توحیدی فر توسعه یافته است. لطفا اگر استفاده کردید و مفید بود دعای خیر فراموش نشود. "
    "راهنما: 1.گزینه های تکبرگ و دوبرگ چه هستند؟ اگر صفحات pdf شما دوبرگ چپ و راست در یک تصویر هستند این گزینه را انتخاب کنید، یا  اگر pdf شما یک برگ در یک تصویر است گزینه تکبرگ را انتخاب کنید. "
    "2.الان در این نسخه (0.001) فقط با مدل GapGPT و GPT-o6 کار می کند. فقط داخل کادر زبان مورد نظرتان را بنویسید، هوش مصنوعی خودش زبان مقصد را تشخیص می دهد. لازم به یادآوری است که باید یک API از GapGPT از نشانی زیر www.gapgpt.ir خریداری کنید. سپاس."
)

        html = f'<!doctype html><html lang="fa"><meta charset="utf-8"><body dir="rtl" style="margin:0;padding:40px;background:#f9f9f9;font-family:Tahoma,sans-serif;"><div style="max-width:650px;margin:0 auto;padding:30px;background:#fff;border-radius:8px;text-align:justify;line-height:1.8;white-space:pre-line;">{help_text}</div></body></html>'

        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".html", delete=False) as f:
                f.write(html)
                help_path = f.name
            if os.path.getsize(help_path) == 0:
                raise OSError("فایل راهنما خالی ایجاد شد.")
            if not webbrowser.open(__import__("pathlib").Path(help_path).as_uri()):
                raise RuntimeError("مرورگر نتوانست فایل راهنما را باز کند.")
        except Exception as e:
            messagebox.showerror("خطای راهنما", f"باز کردن راهنما ناموفق بود: {e}")

    def _set_phase(self, phase):
        """فعال/غیرفعال کردن دکمه‌ها بر اساس مرحله جاری"""
        self.current_phase = phase
        running = phase is not None
        self.btn_stop.config(state=tk.NORMAL if running else tk.DISABLED)
        self.btn_extract.config(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_ocr.config(state=tk.DISABLED if running else
                            (tk.NORMAL if self.page_images else tk.DISABLED))
        self.btn_translate.config(state=tk.DISABLED if running else
                                  (tk.NORMAL if self.ocr_texts else tk.DISABLED))
        if running:
            self.lbl_global_status.config(text=f"در حال اجرا: {phase}")
        else:
            self.lbl_global_status.config(text="آماده")

    def _save_partial(self, filename, content):
        path = os.path.join(self.partial_output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path


    def _start_extract(self):
        path = self.pdf_path.get().strip()
        if not path:
            messagebox.showwarning("خطا", "لطفاً ابتدا فایل PDF را انتخاب کنید.")
            return
        try:
            start = self.start_page.get()
            end = self.end_page.get()
        except tk.TclError:
            messagebox.showwarning("خطا", "شماره صفحات معتبر نیست.")
            return
        if end < start:
            messagebox.showwarning("خطا", "صفحه پایانی نباید کمتر از صفحه شروع باشد.")
            return

        self.stop_event.clear()
        self._set_phase("extract")
        self.page_images = []
        self.worker_thread = threading.Thread(
            target=self._extract_worker, args=(path, start, end), daemon=True)
        self.worker_thread.start()

    def _extract_worker(self, path, start, end):
        try:
            doc = pymupdf.open(path)
            start_idx = max(0, start - 1)
            end_idx = min(end, doc.page_count)
            total_pages = end_idx - start_idx

            split_mode = self.split_mode.get()
            total_halves = total_pages * (2 if split_mode == "double" else 1)
            self.root.after(0, lambda: self.pb_extract.config(maximum=total_halves, value=0))

            out_dir = os.path.join(self.partial_output_dir, "pages_png")
            os.makedirs(out_dir, exist_ok=True)
            counter = 0

            for pno in range(start_idx, end_idx):
                if self.stop_event.is_set():
                    break
                page = doc[pno]
                pix = page.get_pixmap(dpi=250)
                img_path_raw = os.path.join(out_dir, f"_raw_{pno+1:04d}.png")
                pix.save(img_path_raw)

                img = cv2.imread(img_path_raw, cv2.IMREAD_GRAYSCALE)
                h, w = img.shape[:2]
                mid = w // 2

                halves = [img[:, :mid], img[:, mid:]] if split_mode == "double" else [img]

                for side_idx, half in enumerate(halves):
                    if self.stop_event.is_set():
                        break
                    processed = self._preprocess(half)
                    counter += 1
                    img_out = os.path.join(out_dir, f"page_{counter:04d}.png")
                    cv2.imwrite(img_out, processed)
                    self.page_images.append(img_out)
                    self.root.after(0, lambda v=counter: self._update_extract(v))


                try:
                    os.remove(img_path_raw)
                except OSError:
                    pass

            doc.close()

            if self.stop_event.is_set():
                partial_info = self._save_partial(
                    "partial_extract.txt",
                    "\n".join(self.page_images)
                )
                self.root.after(0, lambda: self.lbl_extract.config(
                    text=f"متوقف شد. {counter} صفحه استخراج شد. فهرست: {partial_info}"))
            else:
                self.root.after(0, lambda: self.lbl_extract.config(
                    text=f"استخراج کامل شد ({counter} نیم‌صفحه)"))
        except Exception as e:
            self.root.after(0, lambda: self.lbl_extract.config(text=f"خطا: {e}"))
        finally:
            self.root.after(0, self._extract_done)

    def _preprocess(self, gray):
        """حذف نویز، آستانه‌گذاری و برش حاشیه"""

        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
 
        bw = cv2.medianBlur(bw, 3)

        coords = cv2.findNonZero(255 - bw)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            pad = 15
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(bw.shape[1], x + w + pad)
            y1 = min(bw.shape[0], y + h + pad)
            bw = bw[y0:y1, x0:x1]
        return bw

    def _update_extract(self, val):
        self.pb_extract['value'] = val
        self.lbl_extract.config(text=f"استخراج: {val}/{self.pb_extract['maximum']}")

    def _extract_done(self):
        self._set_phase(None)
        if self.page_images:
            self.btn_ocr.config(state=tk.NORMAL)


    def _start_ocr(self):
        if not self.page_images:
            messagebox.showwarning("خطا", "ابتدا مرحله استخراج را اجرا کنید.")
            return
        self.stop_event.clear()
        self._set_phase("ocr")
        self.ocr_texts = []
        self.worker_thread = threading.Thread(target=self._ocr_worker, daemon=True)
        self.worker_thread.start()

    def _ocr_worker(self):
        total = len(self.page_images)
        self.root.after(0, lambda: self.pb_ocr.config(maximum=total, value=0))
        try:
            for i, f in enumerate(self.page_images):
                if self.stop_event.is_set():
                    break
                img = Image.open(f)
                text = pytesseract.image_to_string(img, lang="deu")
                self.ocr_texts.append(text)
                self.root.after(0, lambda v=i+1: self._update_ocr(v, total))

            full = "\n\n--- صفحه بعد ---\n\n".join(self.ocr_texts)

            if self.stop_event.is_set():
                path = self._save_partial("partial_ocr.txt", full)
                self.root.after(0, lambda: self.lbl_ocr.config(
                    text=f"متوقف شد. {len(self.ocr_texts)}/{total} صفحه OCR شد. ذخیره: {path}"))
                self.root.after(0, lambda: self._show_text(full))
            else:
                self.root.after(0, lambda: self.lbl_ocr.config(text="OCR کامل شد"))
                self.root.after(0, lambda: self._show_text(full))
        except Exception as e:
            self.root.after(0, lambda: self.lbl_ocr.config(text=f"خطا: {e}"))
        finally:
            self.root.after(0, self._ocr_done)

    def _update_ocr(self, val, total):
        self.pb_ocr['value'] = val
        self.lbl_ocr.config(text=f"OCR: {val}/{total}")

    def _ocr_done(self):
        self._set_phase(None)
        if self.ocr_texts:
            self.btn_translate.config(state=tk.NORMAL)
            self.btn_save.config(state=tk.NORMAL)


    def _start_translate(self):
        key = self.api_key.get().strip()
        if not key:
            messagebox.showwarning("خطا", "لطفاً API Key را وارد کنید.")
            return
        if not self.ocr_texts:
            messagebox.showwarning("خطا", "ابتدا مرحله OCR را اجرا کنید.")
            return
        self.stop_event.clear()
        self._set_phase("translate")
        self.worker_thread = threading.Thread(
            target=self._translate_worker, args=(key,), daemon=True)
        self.worker_thread.start()

    def _translate_worker(self, api_key):
        full = "\n\n".join(self.ocr_texts)

        chunks = [full[i:i+3000] for i in range(0, len(full), 3000)]
        total = len(chunks)
        self.root.after(0, lambda: self.pb_translate.config(maximum=total, value=0))
        translated = []
        try:
            for i, chunk in enumerate(chunks):
                if self.stop_event.is_set():
                    break
                try:
                    resp = requests.post(
                        "https://gapgpt.app/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "gpt-3.5-turbo",
                            "messages": [{
                                "role": "user",
                                "content": f"این متن آلمانی را به {self.target_lang.get()} روان و دقیق ترجمه کن:\n\n{chunk}"
                            }]
                        },
                        timeout=120
                    )
                    data = resp.json()
                    translated.append(data["choices"][0]["message"]["content"])
                except Exception as e:
                    translated.append(f"[خطای ترجمه بخش {i+1}: {e}]")
                self.root.after(0, lambda v=i+1: self._update_translate(v, total))

            result = "\n\n".join(translated)

            if self.stop_event.is_set():
                path = self._save_partial("partial_translate.txt", result)
                self.root.after(0, lambda: self.lbl_translate.config(
                    text=f"متوقف شد. {len(translated)}/{total} بخش ترجمه شد. ذخیره: {path}"))
                self.root.after(0, lambda: self._show_text(result))
            else:
                self.root.after(0, lambda: self.lbl_translate.config(text="ترجمه کامل شد"))
                self.root.after(0, lambda: self._show_text(result))
        except Exception as e:
            self.root.after(0, lambda: self.lbl_translate.config(text=f"خطا: {e}"))
        finally:
            self.root.after(0, self._translate_done)

    def _update_translate(self, val, total):
        self.pb_translate['value'] = val
        self.lbl_translate.config(text=f"ترجمه: {val}/{total}")

    def _translate_done(self):
        self._set_phase(None)
        self.btn_save.config(state=tk.NORMAL)

    def _show_text(self, text):
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)
        self.btn_save.config(state=tk.NORMAL)

    def _save_text(self):
        content = self.output.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("اطلاع", "متنی برای ذخیره وجود ندارد.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("ذخیره شد", f"متن در مسیر زیر ذخیره شد:\n{filepath}")
            except Exception as e:
                messagebox.showerror("خطا", f"ذخیره ناموفق: {e}")

    def _request_stop(self):
        if not self.current_phase:
            return
        phase_fa = {"extract": "استخراج", "ocr": "OCR", "translate": "ترجمه"}.get(
            self.current_phase, self.current_phase)
        if messagebox.askyesno(
            "تأیید توقف",
            f"مرحله {phase_fa} در حال اجراست.\nآیا مطمئن هستید که می‌خواهید متوقف کنید؟\n"
            f"داده‌های پردازش شده ذخیره خواهند شد."
        ):
            self.stop_event.set()
            self.lbl_global_status.config(text="در حال توقف، لطفاً صبر کنید...")
            self.btn_stop.config(state=tk.DISABLED)

    def _confirm_exit(self):
        if self.current_phase:
            msg = ("یک عملیات در حال اجراست.\n"
                   "با خروج، عملیات متوقف شده و داده‌های پردازش‌شده ذخیره می‌شوند.\n"
                   "آیا مطمئن هستید؟")
        else:
            msg = "آیا مطمئن هستید که می‌خواهید از برنامه خارج شوید؟"
        if messagebox.askyesno("تأیید خروج", msg):
            if self.current_phase:
                self.stop_event.set()
                if self.worker_thread and self.worker_thread.is_alive():
                    self.worker_thread.join(timeout=15)
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SezginApp(root)
    root.mainloop()
