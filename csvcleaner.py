import streamlit as st
import pandas as pd
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from pathlib import Path
import tempfile

st.set_page_config(page_title="Business Contact Cleaner", page_icon="📂", layout="wide")
st.title("📂 Business Contact Cleaner")

st.markdown("""
Upload one or more **CSV or Excel (.xlsx/.xls)** files.

This app will:
- Keep only **Email**, **BusinessName**, and **Telephone**
- Drop entries with missing or invalid emails (like `NaN`, `null`, or blank)
- Reorder columns as **Email → BusinessName → Telephone**
- Let you download cleaned files or a combined master list
""")

# File uploader
uploaded_files = st.file_uploader("📤 Upload files", type=["csv", "xlsx", "xls"], accept_multiple_files=True)

# --- Helper functions ---
def detect_header_row(df_no_header):
    """Return index of likely header row."""
    search_headers = {"businessname", "business name", "email", "telephone", "phone", "tel"}
    for idx, row in df_no_header.iterrows():
        combined = " ".join([str(x).strip().lower() for x in row.astype(str).tolist()])
        if any(tok in combined for tok in search_headers):
            return idx
    return 0  # fallback if not found

def normalize_and_map_columns(df):
    """Map columns case-insensitively to Email, BusinessName, Telephone."""
    col_map = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in ("email", "e-mail", "emailaddress", "email address"):
            col_map[col] = "Email"
        elif key in ("businessname", "business name", "business", "company", "companyname"):
            col_map[col] = "BusinessName"
        elif key in ("telephone", "tel", "phone", "contactnumber", "contact"):
            col_map[col] = "Telephone"
    return df.rename(columns=col_map)

def clean_dataframe(file_buffer, filename):
    """Clean a single uploaded file."""
    # Read raw to detect header
    if filename.lower().endswith(".csv"):
        raw = pd.read_csv(file_buffer, header=None, dtype=str, encoding="utf-8", encoding_errors="replace")
    else:
        raw = pd.read_excel(file_buffer, header=None, dtype=str)

    header_idx = detect_header_row(raw)

    # Reset buffer to beginning before re-reading
    file_buffer.seek(0)
    
    # Re-read using the detected header
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(file_buffer, header=header_idx, dtype=str, encoding="utf-8", encoding_errors="replace")
    else:
        df = pd.read_excel(file_buffer, header=header_idx, dtype=str)

    # Map columns to standard names
    df = normalize_and_map_columns(df)

    # Ensure required columns exist
    required = ["Email", "BusinessName", "Telephone"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Keep only required columns
    cleaned = df[required].copy()

    # --- Drop invalid / null / blank emails properly ---
    cleaned = cleaned.dropna(subset=["Email"])
    cleaned["Email"] = cleaned["Email"].astype(str).str.strip()
    cleaned = cleaned[cleaned["Email"].ne("")]
    cleaned = cleaned[~cleaned["Email"].str.lower().isin(["nan", "none", "null", "na"])]

    # Clean whitespace from other columns
    for col in ["BusinessName", "Telephone"]:
        cleaned[col] = cleaned[col].astype(str).str.strip()

    # Reorder columns
    cleaned = cleaned[["Email", "BusinessName", "Telephone"]].reset_index(drop=True)

    return cleaned


# --- Process uploaded files ---
if uploaded_files:
    all_cleaned = []
    zip_buffer = BytesIO()

    with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as zipf, tempfile.TemporaryDirectory() as tmpdir:
        for uploaded in uploaded_files:
            try:
                # Need to re-read each file as a fresh BytesIO buffer
                file_bytes = uploaded.read()
                buffer = BytesIO(file_bytes)

                cleaned_df = clean_dataframe(buffer, uploaded.name)
                all_cleaned.append((uploaded.name, cleaned_df))

                # Save individual cleaned CSV
                out_name = Path(uploaded.name).stem + "_cleaned.csv"
                out_path = Path(tmpdir) / out_name
                cleaned_df.to_csv(out_path, index=False)
                zipf.write(out_path, arcname=out_name)

                st.success(f"✅ Processed {uploaded.name} — {len(cleaned_df)} valid rows.")
                st.dataframe(cleaned_df.head(10), use_container_width=True)

                csv_bytes = cleaned_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"📥 Download {out_name}",
                    data=csv_bytes,
                    file_name=out_name,
                    mime="text/csv"
                )

            except Exception as e:
                st.error(f"❌ Error processing {uploaded.name}: {e}")

        # --- Combined cleaned output ---
        if all_cleaned:
            st.markdown("---")
            st.subheader("📦 Combined Cleaned Data")

            combined_df = pd.concat([df for _, df in all_cleaned], ignore_index=True)

            st.write(f"**Total combined rows:** {len(combined_df)}")
            st.dataframe(combined_df.head(20), use_container_width=True)

            combined_csv = combined_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Combined CSV",
                data=combined_csv,
                file_name="combined_cleaned.csv",
                mime="text/csv"
            )

            zip_buffer.seek(0)
            st.download_button(
                "📦 Download All Cleaned Files (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="all_cleaned_files.zip",
                mime="application/zip"
            )
else:
    st.info("👆 Upload one or more files to start cleaning.")
