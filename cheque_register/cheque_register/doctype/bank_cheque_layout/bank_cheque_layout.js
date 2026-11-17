frappe.ui.form.on("Bank Cheque Layout", {
	refresh(frm) { render_cheque_live_preview(frm); },
	cheque_sample_image(frm) { render_cheque_live_preview(frm); },
	page_width_mm(frm) { render_cheque_live_preview(frm); },
	page_height_mm(frm) { render_cheque_live_preview(frm); },
	date_top_mm(frm) { render_cheque_live_preview(frm); },
	date_left_mm(frm) { render_cheque_live_preview(frm); },
	date_letter_spacing_mm(frm) { render_cheque_live_preview(frm); },
	date_font_size(frm) { render_cheque_live_preview(frm); },
	payee_top_mm(frm) { render_cheque_live_preview(frm); },
	payee_left_mm(frm) { render_cheque_live_preview(frm); },
	payee_width_mm(frm) { render_cheque_live_preview(frm); },
	payee_font_size(frm) { render_cheque_live_preview(frm); },
	words_top_mm(frm) { render_cheque_live_preview(frm); },
	words_left_mm(frm) { render_cheque_live_preview(frm); },
	words_width_mm(frm) { render_cheque_live_preview(frm); },
	words_line_height_mm(frm) { render_cheque_live_preview(frm); },
	words_font_size(frm) { render_cheque_live_preview(frm); },
	amount_top_mm(frm) { render_cheque_live_preview(frm); },
	amount_left_mm(frm) { render_cheque_live_preview(frm); },
	amount_font_size(frm) { render_cheque_live_preview(frm); },
	ac_payee_top_mm(frm) { render_cheque_live_preview(frm); },
	ac_payee_left_mm(frm) { render_cheque_live_preview(frm); }
});

function render_cheque_live_preview(frm) {
	if (!frm.fields_dict.live_preview_html) return;

	const d = frm.doc;
	const w = parseFloat(d.page_width_mm) || 195;
	const h = parseFloat(d.page_height_mm) || 85;
	const imgUrl = d.cheque_sample_image ? encodeURI(d.cheque_sample_image) : "";

	const html = `
		<style>
			#live-cheque-canvas, #live-cheque-canvas * {
				box-sizing: border-box !important;
			}
			#live-cheque-canvas {
				position: relative;
				width: ${w}mm !important;
				min-width: ${w}mm !important;
				height: ${h}mm !important;
				min-height: ${h}mm !important;
				background-color: #eef6f9;
				border: 1px solid #64748b;
				box-shadow: 0 6px 20px rgba(0,0,0,0.15);
				font-family: 'Courier New', Courier, monospace !important;
				font-weight: bold !important;
				color: #000000 !important;
				overflow: hidden;
				text-align: left;
				user-select: none;
			}
			#live-cheque-canvas .cheque-bg-img {
				position: absolute;
				top: 0;
				left: 0;
				width: 100%;
				height: 100%;
				object-fit: fill;
				z-index: 1;
				pointer-events: none;
			}
			#live-cheque-canvas .drag-item {
				position: absolute;
				z-index: 5;
				margin: 0 !important;
				padding: 0 !important;
				line-height: 1.42857 !important;
				cursor: move;
				background: rgba(255, 255, 0, 0.35);
				outline: 1px dashed rgba(202, 138, 4, 0.6);
			}
			#live-cheque-canvas .drag-item:focus {
				outline: 1.5px solid #dc2626;
				background: rgba(254, 240, 138, 0.6);
			}
		</style>
		<div style="padding: 15px; background: #f1f5f9; border-radius: 8px; overflow-x: auto;">
			<div style="font-size: 12px; color: #334155; margin-bottom: 10px;">
				<strong>Tip:</strong> লেখাগুলো মাউস দিয়ে টেনে (Drag) বক্সে বসান। আরও সূক্ষ্মভাবে সরাতে লেখার ওপর ক্লিক করে কিবোর্ডের <code>↑ ↓ ← →</code> (Arrow Keys) চাপুন।
			</div>
			<div id="live-cheque-canvas">
				${imgUrl ? `<img class="cheque-bg-img" src="${imgUrl}" alt="Cheque" />` : ""}

				<div tabindex="0" class="drag-item" data-top="ac_payee_top_mm" data-left="ac_payee_left_mm" style="
					top: ${d.ac_payee_top_mm || 12}mm;
					left: ${d.ac_payee_left_mm || 14}mm;
					border-top: 1.5px solid #000;
					border-bottom: 1.5px solid #000;
					width: 58mm;
					text-align: center;
					padding: 1.5px 0 !important;
					font-family: Arial, Helvetica, sans-serif !important;
					font-size: 9.5px;
					letter-spacing: 1.2px;
					transform: rotate(-38deg);
					white-space: nowrap;
				">A/C PAYEE ONLY</div>

				<div tabindex="0" class="drag-item" data-top="date_top_mm" data-left="date_left_mm" style="
					top: ${d.date_top_mm || 11}mm;
					left: ${d.date_left_mm || 144}mm;
					font-size: ${d.date_font_size || 14}px;
					letter-spacing: ${d.date_letter_spacing_mm || 3.4}mm;
				">17112026</div>

				<div tabindex="0" class="drag-item" data-top="payee_top_mm" data-left="payee_left_mm" style="
					top: ${d.payee_top_mm || 24}mm;
					left: ${d.payee_left_mm || 24}mm;
					width: ${d.payee_width_mm || 145}mm;
					font-size: ${d.payee_font_size || 13}px;
					white-space: nowrap;
					overflow: hidden;
				">**A & A Tex Sourcing**</div>

				<div tabindex="0" class="drag-item" data-top="words_top_mm" data-left="words_left_mm" style="
					top: ${d.words_top_mm || 34}mm;
					left: ${d.words_left_mm || 32}mm;
					width: ${d.words_width_mm || 102}mm;
					line-height: ${d.words_line_height_mm || 8.5}mm !important;
					font-size: ${d.words_font_size || 12}px;
					word-wrap: break-word;
				">**One Lakh Fifty Thousand Taka Only**</div>

				<div tabindex="0" class="drag-item" data-top="amount_top_mm" data-left="amount_left_mm" style="
					top: ${d.amount_top_mm || 36}mm;
					left: ${d.amount_left_mm || 146}mm;
					font-size: ${d.amount_font_size || 14}px;
				">**150,000.00/=</div>
			</div>
		</div>
	`;

	const wrapper = frm.fields_dict.live_preview_html.$wrapper;
	wrapper.html(html);

	const canvas = wrapper.find("#live-cheque-canvas")[0];
	if (!canvas) return;

	wrapper.find(".drag-item").on("mousedown", function(e) {
		e.preventDefault();
		this.focus();
		const el = this;
		const pxPerMmX = canvas.clientWidth / w;
		const pxPerMmY = canvas.clientHeight / h;

		const startX = e.clientX;
		const startY = e.clientY;
		const origLeft = el.offsetLeft;
		const origTop = el.offsetTop;

		function onMove(ev) {
			const newLeftPx = origLeft + (ev.clientX - startX);
			const newTopPx = origTop + (ev.clientY - startY);
			el.style.left = newLeftPx + "px";
			el.style.top = newTopPx + "px";
		}

		function onUp() {
			document.removeEventListener("mousemove", onMove);
			document.removeEventListener("mouseup", onUp);
			const finalLeftMm = Math.round((el.offsetLeft / pxPerMmX) * 10) / 10;
			const finalTopMm = Math.round((el.offsetTop / pxPerMmY) * 10) / 10;
			frm.set_value(el.dataset.left, finalLeftMm);
			frm.set_value(el.dataset.top, finalTopMm);
		}

		document.addEventListener("mousemove", onMove);
		document.addEventListener("mouseup", onUp);
	});

	wrapper.find(".drag-item").on("keydown", function(e) {
		const step = 0.2;
		const topField = this.dataset.top;
		const leftField = this.dataset.left;
		let curTop = parseFloat(frm.doc[topField]) || 0;
		let curLeft = parseFloat(frm.doc[leftField]) || 0;

		if (e.key === "ArrowUp") { e.preventDefault(); frm.set_value(topField, Math.round((curTop - step) * 10) / 10); }
		else if (e.key === "ArrowDown") { e.preventDefault(); frm.set_value(topField, Math.round((curTop + step) * 10) / 10); }
		else if (e.key === "ArrowLeft") { e.preventDefault(); frm.set_value(leftField, Math.round((curLeft - step) * 10) / 10); }
		else if (e.key === "ArrowRight") { e.preventDefault(); frm.set_value(leftField, Math.round((curLeft + step) * 10) / 10); }
	});
}
