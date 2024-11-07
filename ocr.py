from paddleocr import PaddleOCR
from pdf2image import convert_from_path
import re, os, json
from collections import Counter

ocr = PaddleOCR(use_angle_cls=True, lang='en')

def detect_document_type(words):
    ktp_keywords = ['NIK', 'PROVINSI', 'KABUPATEN', 'NAMA']
    npwp_keywords = ['NPWP', 'npwp', 'Ddjp', 'KPP', 'KEMENTERIANKEUANGANREPUBLIKINDONESIA','DIREKTORATJENDERALPAJAK','KEMENTERIAN KEUANGANREPUBLK INDONESIA','DIREKTORAT JENDERALPAJAK']
    npwp_pattern = r'\bNPWP(\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3})\b'
    compiled_pattern = re.compile(npwp_pattern)
    
    ktp_count = sum(1 for word in words if word.upper() in ktp_keywords)
    npwp_count = sum(1 for word in words if word.upper() in npwp_keywords)
    text = ' '.join(words)
    npwp_match = compiled_pattern.search(text)
    
    if npwp_match:
        return 'NPWP'
    elif npwp_count > ktp_count:
        return 'NPWP'
    else:
        return 'KTP'


def pdf_to_images(pdf_path, output_folder):
    """Convert PDF pages to images."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    images = convert_from_path(pdf_path)
    image_paths = []

    for i, image in enumerate(images):
        image_path = os.path.join(output_folder, f'page{i+1}.png')
        image.save(image_path, 'PNG')
        image_paths.append(image_path)

    return image_paths

def extract_text_from_images(image_paths):
    """Extract text from list of image paths and return as a list of words, removing colons and spaces."""
    all_words = []

    for image_index, image_path in enumerate(image_paths):
        ocr_result = ocr.ocr(image_path, cls=True)
        
        # Extract and collect text from OCR result
        for line_index, line in enumerate(ocr_result):
            for word_index, word_info in enumerate(line):
                word = word_info[1][0]  # Get the recognized word
                cleaned_word = word.replace(':', '').strip()  # Remove colons and strip spaces
                if cleaned_word:  # Ensure non-empty word is added
                    all_words.append(cleaned_word)
    
    return all_words


def add_spaces_based_on_index(text):
    split_indices = [6, 14]  # Based on the known lengths of segments
    
    # Insert spaces based on these indices
    segments = []
    start = 0
    for index in split_indices:
        segments.append(text[start:index])
        start = index
    segments.append(text[start:])  # Add the last segment

    # Join the segments with spaces
    spaced_text = ' '.join(segments)
    
    return spaced_text

def format_and_split(text):
    if not isinstance(text, str):
        raise ValueError("Input to format_and_split must be a string.")
    text = re.sub(r'\bPROVINSL?\s*([A-Z]+)', r'PROVINSI \1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bPROVINSI I\s*([A-Z]+)', r'PROVINSI \1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bPROVINSI I([A-Z]+)', r'PROVINSI \1', text, flags=re.IGNORECASE)
    #text = re.sub(r'\bPROVINSL([A-Z]+)', 'PROVINSI \1', text, flags=re.IGNORECASE)
    # text = re.sub(r'\bPROVINSE([A-Z]+)', 'PROVINSI \1', text, flags=re.IGNORECASE)
    # text = re.sub(r'\bPROVINSI([A-Z]+)', 'PROVINSI \1', text, flags=re.IGNORECASE)
    # text = re.sub(r'\bPROVINST([A-Z]+)', 'PROVINSI \1', text, flags=re.IGNORECASE)
    #text = re.sub(r'\bPROVIN([A-Z]+)', 'PROVINSI \1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bSEUMURHIDUP\b', 'SEUMUR HIDUP', text, flags=re.IGNORECASE)

    fields = [
        'Provinsi', 'Tempat/Tgl Lahir', 'Status Perkawinan', 'Kewarganegaraan',
        'KOTA', 'Gol\.Darah', 'Kel/Desa', 'Kecamatan', 'Agama', 'Pekerjaan', 
        'Alamat', 'RT/RW', 'Jenis Kelamin', 'NIK', 'Nama', 'Berlaku Hingga'
    ]
    
    # Add space after field names if they are directly followed by a non-space character
    for field in fields:
        escaped_field = re.escape(field)
        text = re.sub(rf'({escaped_field})([^\s,])', r'\1, \2', text, flags=re.IGNORECASE)

    # Handle specific merged terms by adding known location names
    text = re.sub(r'(DAERAH)([A-Z])', r'\1 \2', text)
    text = re.sub(r'(KABUPATEN)([A-Z])', r'\1 \2', text)
    text = re.sub(r'(KOTA)([A-Z])', r'\1 \2', text)

    # Handle more general cases for concatenated terms
    text = re.sub(r'(\b[A-Z]+)([A-Z][a-z])', r'\1 \2', text)
    
    # Fix specific cases where dates and other values are merged
    text = re.sub(r'(\b\d{2})(\d{2}-\d{4})', r'\1-\2', text)

    # Correct common misspellings of "LAKI-LAKI"
    text = re.sub(r'\bLAKI[LRE]LAKI\b', 'LAKI-LAKI', text, flags=re.IGNORECASE)

    # Split the text by commas and clean up extra spaces
    parts = [part.strip() for part in re.split(r',\s*', text)]
    
    return parts

def correct_rt_rw(rt_rw_data):
    # Remove non-digit characters
    digits = re.sub(r'\D', '', rt_rw_data)
    
    # Format RT/RW based on cleaned digits
    if len(digits) == 7:
        # Handle case with 7 digits (remove the middle digit as OCR error)
        rt = digits[:3]
        rw = digits[4:]
        return f"{rt}/{rw}"
    elif len(digits) == 6:
        # Handle case with 6 digits
        rt = digits[:3]
        rw = digits[3:]
        return f"{rt}/{rw}"
    else:
        return rt_rw_data

def extract_npwp(data):
    npwp_pattern = r'(NPWP)(\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3})'

    for value in data:
        match = re.search(npwp_pattern, value)
        if match:
            # Return the split result
            return [match.group(1), match.group(2)]  # Return 'NPWP' and the number
    return None

def clean_npwp_data(data):
    # Remove any entries that start with 'KPP' or 'NPWP'
    cleaned_data = [item for item in data if not (item.startswith('KPP') or item.startswith('NPWP'))]

    # Find the index of the item containing 'TanggalTerdaftar'
    for index, item in enumerate(cleaned_data):
        if 'TanggalTerdaftar' in item:
            # Slice the list to keep only elements up to 'TanggalTerdaftar'
            cleaned_data = cleaned_data[:index]
            break

    return cleaned_data

def npwp_separator(data):
    # Regular expression patterns
    npwp_pattern = re.compile(r'(\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3})')
    np4p_pattern = re.compile(r'NP4P(\d{18})')
    rt_rw_pattern = re.compile(r'RT\.(\d+)\s*RW\.(\d+)')

    cleaned_data = {}
    address = []

    for item in data:
        if npwp_pattern.search(item):
            cleaned_data['NPWP'] = item
        elif np4p_pattern.search(item):
            continue  # Skip NP4P items
        elif item.startswith('KPP'):
            continue  # Skip items starting with KPP
        elif 'Tanggal Terdaftar' in item:
            date_match = re.search(r'Tanggal Terdaftar(\d{2}/\d{2}/\d{4})', item)
            if date_match:
                cleaned_data['TanggalTerdaftar'] = date_match.group(1)
        elif not cleaned_data.get('Nama'):
            cleaned_data['Nama'] = item
        else:
            address.append(item)

    # Process address
    if address:
        full_address = ' '.join(address)
        rt_rw_match = rt_rw_pattern.search(full_address)
        if rt_rw_match:
            rt, rw = rt_rw_match.groups()
            full_address = rt_rw_pattern.sub(f'RT. {rt} RW. {rw}', full_address)
        
        # Split address into components
        address_parts = full_address.split(',') if ',' in full_address else full_address.split()
        
        cleaned_data['Alamat'] = address_parts[0] if len(address_parts) > 0 else ''
        cleaned_data['Kel/Desa'] = address_parts[1] if len(address_parts) > 1 else ''
        cleaned_data['Kota/Kab'] = ' '.join(address_parts[2:]) if len(address_parts) > 2 else ''

    return cleaned_data

def split_address(address):
    patterns = [
        (r'\bJL\b', 'JL. '),
        (r'\bJALAN\b', 'JALAN '),
        (r'\bRT\b', ' RT. '),
        (r'\bRW\b', ' RW. '),
        (r'\bKEL\b', ' KEL. '),
        (r'\bKEC\b', ' KEC. '),
        (r'\bKOTA\b', ' KOTA '),
        (r'\bKAB\b', ' KAB. '),
        (r'\bDESA\b', ' DESA '),
        (r'\bNO\.?\b', ' NO. ')
    ]
    
    # Apply replacement patterns
    for pattern, replacement in patterns:
        address = re.sub(pattern, replacement, address)
    
    # Split the address into words
    words = address.split()
    
    # Determine which words to avoid splitting by identifying frequently occurring terms or common address components
    word_count = Counter(words)
    
    # Dynamically find words to avoid splitting if they are frequent or address-specific
    avoid_splitting = {word for word in words if word_count[word] > 1 or len(word) < 5}
    
    # Process each word
    new_words = []
    skip_next = False
    for i, word in enumerate(words):
        if skip_next:
            skip_next = False
            continue
        
        if word in ['JL.', 'JALAN']:
  
            new_words.append(word)
            if i + 1 < len(words):
                new_words.append(words[i+1])
                skip_next = True
        elif (len(word) > 15 and 
              not any(word.startswith(prefix) for prefix in ['RT.', 'RW.', 'KEL.', 'KEC.', 'KOTA', 'KAB.', 'DESA']) and 
              word not in avoid_splitting):
            # Split long words, but not if they start with specific prefixes or are in avoid_splitting set
            split_word = re.findall('[A-Z][^A-Z]*', word)
            new_words.extend(split_word)
        else:
            new_words.append(word)
    
    # Join the words and remove double spaces
    address = ' '.join(new_words)
    address = re.sub(r'\s+', ' ', address).strip()
    
    return address

def clean_address(parts):
    cleaned = ' '.join(parts)
    cleaned = re.sub(r'\s+', ' ', cleaned)  # Replace multiple spaces with a single space
    return cleaned.strip() 

def process_data(data):

    entries_to_remove = [
        "KEMENTERIANKEUANGANREPUBLIKINDONESIA",
        'KEMENTERIAN KEUANGANREPUBLK INDONESIA', 
        "DIREKTORATJENDERGALPAJAK", 
        "DIREKTORATJENDERALPAJAK",
        'KEMENTERIAN KEUANGAN REPUBLIK INDONESIA', 
        'DIREKTORAT JENDERAL PAJAK',
        'DIREKTORAT JENDERALPAJAK',
        'DIREKTORATJENDERAL PAJAK',
    ]
    
    def normalize_entry(entry):
        return entry.replace(' ', '').upper()
    
    # Define regex patterns to capture different NPWP formats
    formatted_npwp_pattern = r'(?i)(NPWP|NP4P)(?:\s*|\.)?(\d{2}\.?\d{3}\.?\d{3}\.?\d{1}-?\d{3}\.?\d{3})'
    unformatted_npwp_pattern = r'(?i)(NPWP|NP4P)(?:\s*|\.)?(\d{15})'
    combined_pattern = r'(?i)(NPWP|NP4P)\s+(\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3})'
    pattern = re.compile(r'TGLTERDAFTAR\d{2}-\d{2}-\d{4}|TGLTERDAFTARx{7,}|TglDaftar\d{10,}|TGLTERDAFTAR\d{2}/\d{2}/\d{4}|TCLTEROATA.*')
    
    formatted_npwp_regex = re.compile(formatted_npwp_pattern)
    unformatted_npwp_regex = re.compile(unformatted_npwp_pattern)
    combined_regex = re.compile(combined_pattern)
    npwp_data = None
    
    for item in data:
        normalized_item = normalize_entry(item)

        # Skip irrelevant entries
        if normalized_item in map(normalize_entry, entries_to_remove):
            continue

        # Match NPWP or NP4P in various formats
        formatted_match = formatted_npwp_regex.search(item)
        unformatted_match = unformatted_npwp_regex.search(item)
        combined_match = combined_regex.search(item)
        
        if formatted_match:
            npwp_data = formatted_match.group(2)
        elif unformatted_match:
            npwp_data = unformatted_match.group(2)
        elif combined_match:
            npwp_data = combined_match.group(2)

        if npwp_data:
            # Remove non-digit characters and format NPWP properly
            npwp_data = re.sub(r'\D', '', npwp_data)
            npwp_data = f"{npwp_data[:2]}.{npwp_data[2:5]}.{npwp_data[5:8]}.{npwp_data[8]}-{npwp_data[9:12]}.{npwp_data[12:]}"
            break

    npwp_index = next((i for i, s in enumerate(data) if 'NPWP' in s or 'NP4P' in s), None)
    try:
        nik_index = data.index('NIK')
    except UnboundLocalError:
        nik_index = None
    except ValueError:
        nik_index = None
    
    name = data[npwp_index + 1] if npwp_index + 1 < len(data) else 'N/A'
    
    if nik_index is not None:

        address_components = data[nik_index + 2:]  # Start from the address after NIK
        alamat = clean_address(address_components) if address_components else 'N/A'
    
        result = {
            'NPWP': npwp_data if npwp_data else 'N/A',
            'NIK': data[nik_index + 2],
            'Nama': name,
            'Alamat': alamat,
        }

    else:
        data = [item for item in data if not pattern.match(item)]
        address_components = data[npwp_index + 2:]  # Start from the address after NIK
        alamat = clean_address(address_components) if address_components else 'N/A'
        result = {
            'NPWP': npwp_data if npwp_data else 'N/A',
            'Nama': name,
            'Alamat': alamat,
        }

    return result

def find_index(data, *values):
    for value in values:
        try:
            return data.index(value) + 1
        except ValueError:
            continue
    return None

def extract_provinsi(data):
    if not isinstance(data, list) or not data:
        return "N/A"
    
    try:
        prov_index = next(i for i, item in enumerate(data) if 'PROVINSI' in item or 'PROPINSI' in item)
        print("Index of 'PROVINSI':", prov_index)
        
        # The value of 'PROVINSI' is in the same element, just remove 'PROVINSI'
        prov_value = data[prov_index].replace('PROVINSI', '').strip().replace('PROPINSI', '').strip()
        
        if prov_value.upper() == "DKIJAKARTA":
            prov_value = "DKI JAKARTA"
        
        # Print extracted value for debugging
        print("Extracted Provinsi Value:", prov_value)
        
        # Return the extracted value or "N/A" if it's empty
        return prov_value if prov_value else "N/A"
    
    except StopIteration:
        return "N/A"

def clean_ocr_output(output):
    cleaned = []
    for item in output:
        # Remove items that start with unwanted prefixes
        if not re.match(r'^(EPP|KPP)\d*', item):
            cleaned.append(item)
    return cleaned

def extract_nik(data):
    pattern = re.compile(r'(NP4P|NPWP)(\d{16}\d*)$')
    
    for i, item in enumerate(data):
        match = pattern.match(str(item))
        if match:
            data[i] = 'NIK'
            number = match.group(2)[-16:]
            data.insert(i+1, number)
    return data

def extract_npwp(data):
    result = []
    npwp_pattern = r'(?i)npwp\s*(\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3})|' \
                   r'(?i)^(npwp\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3})$'

    for i, value in enumerate(data):
        # Check for the NPWP pattern directly in the value
        match = re.search(npwp_pattern, value)
        if match:
            result.append('npwp')  # Add 'npwp'
            if match.group(1):  # Check for captured NPWP
                result.append(match.group(1))  # Add NPWP number
            elif match.group(0):  # If NPWP is directly in the string
                result.append(match.group(0)[5:])  # Extract NPWP part
            
            # Add subsequent data
            next_index = i + 1
            while next_index < len(data):
                result.append(data[next_index])
                next_index += 1
            break  # Stop after finding 'npwp'

    return result if result else None

def split_npwp(data):
    result = []
    # Regex to match the combined NPWP pattern
    combined_pattern = re.compile(r'(?i)^(npwp)(\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3})$')
    
    for item in data:
        # Check if the item matches the combined NPWP format
        match = combined_pattern.match(item)
        
        if match:
            # If matched, split into separate 'npwp' and number entries
            result.append(match.group(1).lower())  # Add 'npwp' in lowercase
            result.append(match.group(2))  # Add the NPWP number
        else:
            # If not matched, keep the item as is
            result.append(item)
    
    return result

def main(file_path, output_folder='images'):
    file_path = os.path.abspath(file_path)  
    print(f"Processing file: {file_path}")  

    # Determine file type and convert to image paths if necessary
    if file_path.lower().endswith('.pdf'):
        image_paths = pdf_to_images(file_path, output_folder)
    elif file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
        image_paths = [os.path.abspath(file_path)]
    else:
        raise ValueError("Unsupported file type. Please provide a PDF or image file.")

    # Extract text from images
    words = extract_text_from_images(image_paths)
    comma_separated_words = ', '.join(words)
    data = format_and_split(comma_separated_words)
    print(data)
    
    patterns = [
        r'\bEPP\w*\b',
        r'\bKPP\w*\b',
    ]
    
    # Compile the patterns into a single regex pattern
    regex_pattern = re.compile('|'.join(patterns), re.IGNORECASE)

    filtered_data = [item.strip() for item in data if not regex_pattern.search(item.strip())]
    print("Filtered Data:", filtered_data)
    
    document_type = detect_document_type(filtered_data)
    
    if document_type == 'NPWP':
        entries_to_remove = ["KEMENTERIANKEUANGANREPUBLIKINDONESIA", 
                        "DIREKTORATJENDERGALPAJAK", 
                        "DIREKTORATJENDERALPAJAK",
                        'KEMENTERIAN KEUANGAN REPUBLIK INDONESIA', 
                        'DIREKTORAT JENDERAL PAJAK','KEMENTERIAN KEUANGANREPUBLK INDONESIA',
                        'DIREKTORAT JENDERALPAJAK','DIREKTORATJENDERAL PAJAK']
        if any(item.strip() in entries_to_remove for item in filtered_data):
            result = process_data(filtered_data)
        ############################################ NPWP ##################################################
        else:
            try:
                filtered_data = split_npwp(filtered_data)
                print("CODE X :  ",filtered_data)
                nik_index = None

                try:
                    npwp_index = next(i for i, item in enumerate(filtered_data) if item.lower() == 'npwp')
                except StopIteration:
                    print("NPWP not found in data.")
                try:
                    filtered_data = extract_nik(filtered_data)
                    nik_index = next(i for i, item in enumerate(filtered_data) if item.lower() == 'nik')
                except StopIteration:
                    print("NIK not found in data.")
                    nik_index = None
                    
                if nik_index is not None:
                    nik_data = filtered_data[nik_index + 1] if npwp_index + 1 < len(filtered_data) else ''
                    # Extract NPWP and its fields
                    npwp_raw = filtered_data[npwp_index + 1] if npwp_index + 1 < len(filtered_data) else ''
                    # Extract the fields, assuming the order of elements remains consistent
                    nama = filtered_data[npwp_index + 2] if npwp_index + 2 < len(filtered_data) else ''
                    alamat_raw = filtered_data[nik_index + 2] if npwp_index + 3 < len(filtered_data) else ''
                    kel_desa = filtered_data[nik_index + 3] if npwp_index + 4 < len(filtered_data) else ''
                    kota_kab = filtered_data[nik_index + 4] if npwp_index + 5 < len(filtered_data) else ''

                    # Create the result dictionary
                    result = {
                        'NPWP': npwp_raw,
                        'NIK': nik_data,  # Placeholder as no NIK is given in the sample data
                        'Nama': nama,
                        'Alamat': alamat_raw,
                        'Kel/Desa': kel_desa,
                        'Kota/Kab': kota_kab,
                    }
                    
                if nik_index is None:
                    npwp_index = next(i for i, item in enumerate(filtered_data) if item.lower() == 'npwp')
                    npwp_raw = filtered_data[npwp_index + 1] if npwp_index is not None and npwp_index + 1 < len(filtered_data) else ''
                    nama = filtered_data[npwp_index + 2] if npwp_index is not None and npwp_index + 2 < len(filtered_data) else ''
                    address_components = filtered_data[npwp_index + 3:] if npwp_index is not None else []  # Start from the address after NIK
                    print(address_components)
                    alamat = clean_address(address_components) if address_components else 'N/A'
                    
                    result = {
                        'NPWP': npwp_raw,
                        'Nama': nama,
                        'Alamat': alamat,
                    }
                    
            except IndexError as e:
                print(f"IndexError: {e}")
            
            except ValueError:
                print("NPWP not found in the filtered data.")
                return None
           
    else:
        print(data)
        try:
            nik_index = data.index('NIK') + 1
        except ValueError:
            nik_index = None
            print("Warning: 'NIK' not found in data.")
    
        try:
            name_index = data.index('Nama') + 1
        except ValueError:
            name_index = None
            print("Warning: 'Nama' not found in data.")
        
        try:
            kel_index = find_index(data,'Kel/Desa','Ke/Desa')
        except ValueError:
            kel_index = None
            print("Warning: 'Kel/Desa' not found in data.")
        
        try:
            kec_index = data.index('Kecamatan') + 1
        except ValueError:
            kec_index = None
            print("Warning: 'Kecamatan' not found in data.")
        
        try:
            rt_rw_index = data.index(next(x for x in data if 'RT/RW' in x or 'RTRW' in x)) + 1
            rt_rw_data = data[rt_rw_index]
            formatted_rt_rw = correct_rt_rw(rt_rw_data)
        except ValueError:
            rt_rw_index = None
            formatted_rt_rw = None
            print("Warning: 'RT/RW' not found in data.")
        
        try:
            alamat_index = data.index('Alamat') + 1
            address_parts = []
            for item in data[alamat_index:rt_rw_index]:
                if item in ['RT/RW', 'RTRW']:
                    break
                address_parts.append(item)
            full_address = ' '.join(address_parts).strip()
        except ValueError:
            alamat_index = None
            full_address = None
            print("Warning: 'Alamat' not found in data.")
        
        # Use None as fallback value if an index is not found
        nik = data[nik_index] if nik_index is not None else "N/A"
        name = data[name_index] if name_index is not None else "N/A"
        kel = data[kel_index] if kel_index is not None else "N/A"
        kec = data[kec_index] if kec_index is not None else "N/A"
        formatted_rt_rw = formatted_rt_rw if "KelDesa" not in formatted_rt_rw else "N/A"

        result = {
            'Provinsi': extract_provinsi(data),
            'Kota/Kab': data[1] if len(data) > 2 else "N/A",
            'NIK': nik,
            'Name': name,
            'Alamat': full_address,
            'RT/RW': formatted_rt_rw if formatted_rt_rw is not None else "N/A",
            'Kelurahan/Desa': kel,
            'Kecamatan': kec
        }


    return result


#################### DEBUGGING ##########################



#     try:
#         output_path = os.path.abspath('output.json')
#         with open(output_path, 'w') as file:
#             json.dump(result, file, separators=(',', ':'))
#             file.flush()  # Ensure all data is written
#     except Exception as e:
#         print(f"Error writing file: {e}")

#     # Check if the file exists and has content
#     if os.path.exists(output_path):
#         with open(output_path, 'r') as file:
#             content = file.read()
#             print(f"File content:\n{content}")
#     else:
#         print(f"File not found at {output_path}")


# # Example usage
# #pdf_path = r'C:\Users\Popo\Desktop\drive-download-20240911T060847Z-001\ktp22.pdf'
# #pdf_path = r'C:\Users\Popo\Desktop\drive-download-20240911T060847Z-001\npwp1.pdf'
# pdf_path = r'C:\Users\Popo\Desktop\drive-download-20240919T044320Z-001\NPWPP2.pdf'
# main(pdf_path)