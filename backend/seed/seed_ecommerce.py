"""
seed_ecommerce.py — Synthetic e-commerce dataset for the QueryLens demo connection.
Uses ONLY the Python standard library; pymongo is needed for MongoDB insertion.

QueryLens discovers the schema automatically by sampling — no schema metadata
is written; the seeded collections are the single source of truth.

Usage:
  python seed/seed_ecommerce.py --uri mongodb://localhost:27017 --db demo_ecommerce --drop
  python seed/seed_ecommerce.py --json-only --output-dir ./data
"""
import argparse, random, json, string, sys
from datetime import datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NUM_CUSTOMERS, NUM_SELLERS, NUM_PRODUCTS, NUM_ORDERS, NUM_REVIEWS = 500, 50, 200, 5000, 3000

CATEGORIES = ["Electronics","Clothing","Home & Garden","Sports & Outdoors","Books","Toys & Games","Beauty & Health","Automotive","Food & Beverages","Office Supplies","Pet Supplies","Jewelry"]
SUB_CATEGORIES = {"Electronics":["Smartphones","Laptops","Headphones","Tablets","Cameras","Smart Watches","Speakers","Monitors"],"Clothing":["T-Shirts","Jeans","Dresses","Jackets","Sneakers","Hats","Socks","Suits"],"Home & Garden":["Furniture","Lighting","Kitchenware","Bedding","Tools","Plants","Decor","Storage"],"Sports & Outdoors":["Fitness Equipment","Camping Gear","Bicycles","Yoga Mats","Running Shoes","Balls","Swimwear"],"Books":["Fiction","Non-Fiction","Science","History","Cooking","Children","Technology","Self-Help"],"Toys & Games":["Board Games","Action Figures","Puzzles","LEGO","Dolls","RC Cars","Card Games"],"Beauty & Health":["Skincare","Makeup","Vitamins","Hair Care","Fragrances","Supplements","First Aid"],"Automotive":["Car Accessories","Tires","Tools","Electronics","Cleaning","Parts","Oils & Fluids"],"Food & Beverages":["Snacks","Coffee & Tea","Organic","Spices","Drinks","Canned Goods","Sweets"],"Office Supplies":["Pens & Pencils","Paper","Binders","Desk Accessories","Printers","Labels","Chairs"],"Pet Supplies":["Dog Food","Cat Food","Toys","Beds","Grooming","Leashes","Aquarium","Bird Supplies"],"Jewelry":["Rings","Necklaces","Bracelets","Earrings","Watches","Brooches","Anklets"]}
ORDER_STATUSES = ["pending","processing","shipped","delivered","cancelled","returned"]
PAYMENT_METHODS = ["credit_card","debit_card","paypal","bank_transfer","cash_on_delivery","crypto"]
SHIPPING_METHODS = ["standard","express","overnight","economy","pickup"]
SHIPPING_COSTS = {"standard":4.99,"express":9.99,"overnight":19.99,"economy":2.99,"pickup":0.0}

COUNTRIES = {"US":["New York","Los Angeles","Chicago","Houston","Phoenix","San Francisco","Seattle","Boston","Miami","Denver"],"UK":["London","Manchester","Birmingham","Leeds","Glasgow","Liverpool","Edinburgh","Bristol"],"DE":["Berlin","Munich","Hamburg","Frankfurt","Stuttgart","Cologne","Düsseldorf","Leipzig"],"FR":["Paris","Lyon","Marseille","Toulouse","Nice","Nantes","Strasbourg","Bordeaux"],"GR":["Athens","Thessaloniki","Patras","Heraklion","Larissa","Volos","Ioannina","Kavala"],"IT":["Rome","Milan","Naples","Turin","Florence","Bologna","Venice","Genoa"],"ES":["Madrid","Barcelona","Valencia","Seville","Bilbao","Malaga","Zaragoza"],"NL":["Amsterdam","Rotterdam","The Hague","Utrecht","Eindhoven","Groningen"],"SE":["Stockholm","Gothenburg","Malmö","Uppsala","Västerås","Örebro"],"JP":["Tokyo","Osaka","Kyoto","Yokohama","Nagoya","Sapporo","Fukuoka","Kobe"],"AU":["Sydney","Melbourne","Brisbane","Perth","Adelaide","Gold Coast","Canberra"],"CA":["Toronto","Vancouver","Montreal","Calgary","Ottawa","Edmonton","Winnipeg"],"BR":["São Paulo","Rio de Janeiro","Brasília","Salvador","Fortaleza","Curitiba"],"MX":["Mexico City","Guadalajara","Monterrey","Cancún","Puebla","Tijuana"],"IN":["Mumbai","Delhi","Bangalore","Hyderabad","Chennai","Kolkata","Pune","Ahmedabad"]}

FIRST_M = ["James","John","Robert","Michael","David","William","Richard","Joseph","Thomas","Daniel","Alexander","Benjamin","Christopher","Ethan","George","Henry","Isaac","Jack","Kevin","Leo","Marcus","Nathan","Oliver","Patrick","Ryan","Samuel","Tyler","Victor","Andreas","Carlos","Dimitri","Eduardo","François","Giovanni","Hans","Ibrahim","Javier","Kenji","Lars","Mateo","Nikolai","Oscar","Paolo","Rafael","Sven","Takeshi","Yuki","Arjun","Wei"]
FIRST_F = ["Mary","Patricia","Jennifer","Linda","Elizabeth","Barbara","Susan","Jessica","Sarah","Karen","Alice","Beatrice","Charlotte","Diana","Elena","Fiona","Grace","Helena","Irene","Julia","Katherine","Laura","Maria","Natalie","Olivia","Penelope","Rachel","Sofia","Victoria","Zoe","Aiko","Brigitte","Chiara","Daphne","Emilia","Freya","Giulia","Hana","Ingrid","Jasmine","Katrina","Lucia","Mika","Nadia","Petra","Rosa","Sakura","Tanya","Uma","Valentina"]
LAST = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez","Anderson","Taylor","Thomas","Moore","Jackson","Martin","Lee","Thompson","White","Harris","Mueller","Schmidt","Schneider","Fischer","Weber","Wagner","Becker","Hoffmann","Koch","Richter","Papadopoulos","Georgiou","Nikolaou","Rossi","Russo","Ferrari","Dupont","Leroy","Moreau","Laurent","Tanaka","Watanabe","Yamamoto","Suzuki","Kim","Park","Chen","Wang","Silva","Santos","Oliveira","Johansson","Eriksson","Petrov","Novak","Kowalski","Patel","Singh","Gupta"]
STREETS = ["Main Street","Oak Avenue","Maple Drive","Cedar Lane","Elm Street","Park Road","Lake View","River Road","Hill Street","Forest Avenue","Sunset Boulevard","Ocean Drive","Spring Lane","Valley Road","Garden Street","King's Road","Queen's Avenue","Market Street","High Street","Station Road","Church Lane","Bridge Street","Mill Lane"]
CO_WORDS = ["Alpha","Beta","Delta","Omega","Nova","Apex","Prime","Metro","Eco","Zenith","Summit","Horizon","Vertex","Stellar","Fusion","Quantum","Nexus","Pulse","Vibe","Core","Swift","Bright","Clear","True","Blue","Green","Golden","Silver","Crystal","Royal"]
CO_SUFFIX = ["Inc.","Ltd.","GmbH","S.A.","Co.","Corp.","LLC","Group","Solutions","Trading","International","Global","Direct","Express","Online","Digital","Tech","Pro"]
PROD_ADJ = ["Premium","Ultra","Pro","Classic","Deluxe","Essential","Advanced","Smart","Eco","Mini","Compact","Turbo","Elite","Luxury","Basic","Super","Mega","Nano","Flex","Max"]
PROD_NOUNS = {"Electronics":["Wireless Charger","Bluetooth Speaker","USB Hub","Power Bank","Webcam","Keyboard","Mouse","Cable","Adapter","Earbuds"],"Clothing":["Cotton Shirt","Denim Jacket","Running Shoes","Wool Sweater","Silk Scarf","Leather Belt","Linen Pants","Sport Socks"],"Home & Garden":["LED Lamp","Throw Pillow","Wall Clock","Plant Pot","Cutting Board","Candle Set","Door Mat","Shelf Unit"],"Sports & Outdoors":["Water Bottle","Resistance Bands","Yoga Mat","Jump Rope","Dumbbell Set","Backpack","Tent","Sleeping Bag"],"Books":["Hardcover Novel","Cookbook","Guide Book","Journal","Planner","Art Book","Textbook","Comic Book"],"Toys & Games":["Building Set","Card Game","Puzzle Box","Action Figure","Board Game","Remote Car","Drone Kit","Science Kit"],"Beauty & Health":["Face Cream","Lip Balm","Shampoo","Sunscreen","Vitamin Pack","Essential Oil","Hair Serum","Body Lotion"],"Automotive":["Phone Mount","Dash Cam","Seat Cover","Air Freshener","Cleaning Kit","Floor Mat","Tool Kit","Jump Starter"],"Food & Beverages":["Coffee Beans","Tea Set","Spice Mix","Protein Bar","Honey Jar","Olive Oil","Snack Box","Chocolate Set"],"Office Supplies":["Notebook","Pen Set","Desk Organizer","Sticky Notes","Tape Dispenser","Stapler","File Folder","Label Maker"],"Pet Supplies":["Dog Toy","Cat Bed","Pet Bowl","Leash Set","Grooming Brush","Treats Bag","Fish Tank","Bird Feeder"],"Jewelry":["Silver Ring","Gold Necklace","Charm Bracelet","Stud Earrings","Crystal Pendant","Pearl Set","Cuff Links","Brooch Pin"]}
REV_POS = ["Excellent quality, exactly what I needed!","Highly recommend this product.","Great value for the price.","Exceeded my expectations.","Fast shipping and perfect product.","Will buy again!","Amazing quality and packaging.","Love it, works as described.","Best purchase this year.","Superb craftsmanship.","Perfect gift idea.","Outstanding, five stars."]
REV_NEG = ["Not as described.","Poor quality material.","Arrived damaged.","Would not recommend.","Very disappointed.","Not worth the price.","Took too long to arrive.","Missing parts.","Much smaller than expected.","Broke after a week.","Color differs from photo.","Feels like a knockoff."]
REV_NEU = ["Okay for the price.","Decent, nothing special.","Average quality.","Does the job.","Nothing special.","As expected.","Fair enough.","Could be better.","Meets basic needs.","Standard quality."]
REV_TITLES = ["Great product","Disappointed","Just okay","Love it","Not worth it","Exceeded expectations","Good value","Could be better","Perfect","Amazing quality","Terrible","Decent purchase","Highly recommend","Waste of money","Solid choice","Beautiful item","Poor quality","As described","Wrong size","Fast delivery"]
FILLER = ["Product arrived quickly and well packaged.","Been using this for several weeks.","My family enjoys this product.","Color matches the listing photos.","Setup was easy and straightforward.","Customer service was helpful.","Compared several options first.","Second purchase from this seller.","Instructions could be clearer.","Solid purchase for everyday use.","Great gift for anyone.","Material feels durable.","Shipping was faster than expected.","Price was reasonable.","Satisfied with this purchase."]

def rdate(s,e):
    return s+timedelta(seconds=random.randint(0,int((e-s).total_seconds())))

def rphone(cc):
    d=''.join(random.choices(string.digits,k=10))
    return f"+{cc}{d}"

def remail(f,l,i):
    doms=["gmail.com","yahoo.com","outlook.com","hotmail.com","protonmail.com","icloud.com","mail.com","zoho.com"]
    sep=random.choice([".","-","_",""])
    suf="" if i<200 else str(i)
    return f"{f.lower()}{sep}{l.lower()}{suf}@{random.choice(doms)}"

def rpost(c):
    if c in("US","MX","DE","FR","IT","ES","GR"): return ''.join(random.choices(string.digits,k=5))
    if c=="UK": return f"{''.join(random.choices(string.ascii_uppercase,k=2))}{random.randint(1,9)} {random.randint(1,9)}{''.join(random.choices(string.ascii_uppercase,k=2))}"
    if c=="JP": return f"{random.randint(100,999)}-{random.randint(1000,9999)}"
    return ''.join(random.choices(string.digits,k=random.choice([4,5])))

def gen_customers(n):
    cs=[]; now=datetime.now()
    for i in range(1,n+1):
        cc=random.choice(list(COUNTRIES.keys())); city=random.choice(COUNTRIES[cc])
        g=random.choices(["male","female","non-binary","prefer_not_to_say"],weights=[45,45,7,3])[0]
        fn=random.choice(FIRST_M if g=="male" else FIRST_F if g=="female" else FIRST_M+FIRST_F)
        ln=random.choice(LAST)
        cs.append({"customer_id":f"CUST-{i:04d}","first_name":fn,"last_name":ln,"email":remail(fn,ln,i),"phone":rphone(cc.replace("UK","44").replace("US","1").replace("DE","49").replace("FR","33").replace("GR","30").replace("IT","39").replace("ES","34").replace("NL","31").replace("SE","46").replace("JP","81").replace("AU","61").replace("CA","1").replace("BR","55").replace("MX","52").replace("IN","91")),"date_of_birth":rdate(datetime(1950,1,1),datetime(2006,1,1)).strftime("%Y-%m-%d"),"gender":g,"address":{"street":f"{random.randint(1,999)} {random.choice(STREETS)}","city":city,"country":cc,"postal_code":rpost(cc)},"registered_at":rdate(now-timedelta(days=1095),now-timedelta(days=30)).isoformat(timespec="seconds"),"is_active":random.random()>0.1,"loyalty_tier":random.choices(["standard","silver","gold","platinum"],weights=[50,30,15,5])[0],"total_spent":0.0,"total_orders":0,"preferred_payment":random.choice(PAYMENT_METHODS),"marketing_consent":random.random()>0.3,"tags":random.sample(["frequent_buyer","deal_hunter","premium","new_customer","returning","high_value","at_risk"],k=random.randint(0,3))})
    return cs

def gen_sellers(n):
    ss=[]; now=datetime.now()
    for i in range(1,n+1):
        cc=random.choice(list(COUNTRIES.keys())); city=random.choice(COUNTRIES[cc])
        w1,w2=random.sample(CO_WORDS,2)
        ss.append({"seller_id":f"SELL-{i:03d}","company_name":f"{w1}{w2} {random.choice(CO_SUFFIX)}","contact_name":f"{random.choice(FIRST_M+FIRST_F)} {random.choice(LAST)}","email":f"contact@{w1.lower()}{w2.lower()}.com","phone":rphone("1"),"address":{"city":city,"country":cc},"joined_at":rdate(now-timedelta(days=1460),now-timedelta(days=60)).isoformat(timespec="seconds"),"is_verified":random.random()>0.2,"tier":random.choices(["bronze","silver","gold","platinum"],weights=[30,35,25,10])[0],"rating":round(random.uniform(2.5,5.0),2),"total_sales":0,"total_revenue":0.0,"categories":random.sample(CATEGORIES,k=random.randint(1,4)),"commission_rate":round(random.uniform(0.05,0.20),2),"return_rate":round(random.uniform(0.01,0.15),3),"avg_shipping_days":random.randint(1,7),"is_active":random.random()>0.05})
    return ss

def gen_products(n,sellers):
    ps=[]; now=datetime.now()
    for i in range(1,n+1):
        cat=random.choice(CATEGORIES); sub=random.choice(SUB_CATEGORIES[cat]); sel=random.choice(sellers)
        bp=round(random.uniform(5,500),2); hd=random.random()>0.7; dp=round(random.uniform(0.05,0.40),2) if hd else 0.0
        adj=random.choice(PROD_ADJ); noun=random.choice(PROD_NOUNS.get(cat,["Item"]))
        ps.append({"product_id":f"PROD-{i:04d}","name":f"{adj} {noun}","description":f"High-quality {noun.lower()} from the {sub.lower()} range. {random.choice(FILLER)}","category":cat,"sub_category":sub,"seller_id":sel["seller_id"],"price":bp,"discount_percentage":dp,"discounted_price":round(bp*(1-dp),2),"currency":"EUR","stock":random.randint(0,500),"rating":round(random.uniform(1,5),1),"review_count":0,"weight_kg":round(random.uniform(0.1,15),2),"dimensions":{"length_cm":round(random.uniform(5,100),1),"width_cm":round(random.uniform(5,80),1),"height_cm":round(random.uniform(2,60),1)},"tags":random.sample(["bestseller","new_arrival","trending","limited_edition","eco_friendly","handmade","imported","organic","sale","exclusive"],k=random.randint(0,4)),"is_available":random.random()>0.08,"created_at":rdate(now-timedelta(days=730),now-timedelta(days=7)).isoformat(timespec="seconds")})
    return ps

def gen_orders(n,customers,products,sellers):
    ords=[]; now=datetime.now()
    for i in range(1,n+1):
        c=random.choice(customers); od=rdate(now-timedelta(days=730),now)
        ni=random.choices([1,2,3,4,5,6],weights=[35,30,18,10,5,2])[0]
        ops=random.sample(products,k=min(ni,len(products)))
        items=[]; sub=0.0; sids=set()
        for p in ops:
            q=random.choices([1,2,3,4,5],weights=[50,25,15,7,3])[0]; up=p["discounted_price"]; it=round(up*q,2); sub+=it; sids.add(p["seller_id"])
            items.append({"product_id":p["product_id"],"product_name":p["name"],"category":p["category"],"seller_id":p["seller_id"],"quantity":q,"unit_price":up,"item_total":it})
        sm=random.choice(SHIPPING_METHODS); sc=SHIPPING_COSTS[sm]; tr=round(random.uniform(0.05,0.25),2); ta=round(sub*tr,2); tot=round(sub+sc+ta,2)
        da=(now-od).days
        if da<2: st=random.choices(["pending","processing"],weights=[60,40])[0]
        elif da<7: st=random.choices(["processing","shipped","delivered"],weights=[20,50,30])[0]
        else: st=random.choices(ORDER_STATUSES,weights=[2,3,10,70,10,5])[0]
        dd=None
        if st=="delivered": dd=(od+timedelta(days=random.randint(1,14))).isoformat(timespec="seconds")
        ords.append({"order_id":f"ORD-{i:05d}","customer_id":c["customer_id"],"customer_name":f"{c['first_name']} {c['last_name']}","customer_country":c["address"]["country"],"order_date":od.isoformat(timespec="seconds"),"status":st,"items":items,"num_items":len(items),"subtotal":round(sub,2),"shipping_method":sm,"shipping_cost":sc,"tax_rate":tr,"tax_amount":ta,"total":tot,"currency":"EUR","payment_method":c["preferred_payment"],"payment_status":"paid" if st!="cancelled" else random.choice(["paid","refunded"]),"shipping_address":c["address"],"delivery_date":dd,"seller_ids":sorted(list(sids)),"notes":random.choice(FILLER) if random.random()>0.85 else None,"is_gift":random.random()>0.9,"coupon_code":f"SAVE{random.choice([10,15,20,25])}" if random.random()>0.8 else None})
    # Update aggregates
    ct={}
    for o in ords:
        cid=o["customer_id"]; ct.setdefault(cid,{"s":0.0,"c":0}); ct[cid]["s"]+=o["total"]; ct[cid]["c"]+=1
    for c in customers:
        if c["customer_id"] in ct: c["total_spent"]=round(ct[c["customer_id"]]["s"],2); c["total_orders"]=ct[c["customer_id"]]["c"]
    st={}
    for o in ords:
        for it in o["items"]:
            sid=it["seller_id"]; st.setdefault(sid,{"s":0,"r":0.0}); st[sid]["s"]+=1; st[sid]["r"]+=it["item_total"]
    for s in sellers:
        if s["seller_id"] in st: s["total_sales"]=st[s["seller_id"]]["s"]; s["total_revenue"]=round(st[s["seller_id"]]["r"],2)
    return ords

def gen_reviews(n,orders,products):
    revs=[]; do=[o for o in orders if o["status"]=="delivered"]
    if not do: return revs
    for i in range(1,n+1):
        o=random.choice(do); it=random.choice(o["items"]); r=random.choices([1,2,3,4,5],weights=[5,8,15,35,37])[0]
        if r>=4: cm=random.choice(REV_POS)+" "+random.choice(FILLER)
        elif r<=2: cm=random.choice(REV_NEG)+" "+random.choice(FILLER)
        else: cm=random.choice(REV_NEU)+" "+random.choice(FILLER)
        rd=datetime.fromisoformat(o["delivery_date"])+timedelta(days=random.randint(1,30)) if o["delivery_date"] else datetime.fromisoformat(o["order_date"])+timedelta(days=random.randint(5,30))
        revs.append({"review_id":f"REV-{i:05d}","order_id":o["order_id"],"product_id":it["product_id"],"customer_id":o["customer_id"],"customer_name":o["customer_name"],"seller_id":it["seller_id"],"rating":r,"title":random.choice(REV_TITLES),"comment":cm,"review_date":rd.isoformat(timespec="seconds"),"verified_purchase":True,"helpful_votes":random.randint(0,50),"images_count":random.choices([0,1,2,3],weights=[60,25,10,5])[0]})
    pr={}; prt={}
    for rv in revs: pr.setdefault(rv["product_id"],0); prt.setdefault(rv["product_id"],[]); pr[rv["product_id"]]+=1; prt[rv["product_id"]].append(rv["rating"])
    for p in products:
        if p["product_id"] in pr: p["review_count"]=pr[p["product_id"]]; p["rating"]=round(sum(prt[p["product_id"]])/len(prt[p["product_id"]]),1)
    return revs

def export_json(data,out):
    p=Path(out); p.mkdir(parents=True,exist_ok=True)
    for name,docs in data.items():
        fp=p/f"{name}.json"
        with open(fp,"w",encoding="utf-8") as f: json.dump(docs,f,indent=2,ensure_ascii=False,default=str)
        print(f"  {len(docs):>6,} docs -> {fp}")

def insert_mongo(data,uri,db_name,drop=False):
    try: from pymongo import MongoClient
    except ImportError: print("  pymongo not installed, skipping MongoDB."); return False
    client=MongoClient(uri); db=client[db_name]
    for name,docs in data.items():
        if drop: db[name].drop()
        if docs: db[name].insert_many(docs); print(f"  {len(docs):>6,} docs -> {name}")
    print("\n  Creating indexes...")
    for col,idxs in {"customers":[("customer_id",True),("address.country",False),("loyalty_tier",False)],"sellers":[("seller_id",True),("tier",False),("rating",False)],"products":[("product_id",True),("category",False),("seller_id",False)],"orders":[("order_id",True),("customer_id",False),("order_date",False),("status",False),("total",False)],"reviews":[("review_id",True),("product_id",False),("rating",False)]}.items():
        for field,uniq in idxs: db[col].create_index(field,unique=uniq)
    print("  Done."); client.close(); return True

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--uri",default="mongodb://localhost:27017"); ap.add_argument("--db",default="demo_ecommerce"); ap.add_argument("--drop",action="store_true"); ap.add_argument("--seed",type=int,default=42); ap.add_argument("--json-only",action="store_true"); ap.add_argument("--output-dir",default="./data"); args=ap.parse_args()
    random.seed(args.seed)
    print("="*60+"\n  QueryLens — Demo Dataset Generator\n"+"="*60)
    print(f"\nGenerating {NUM_CUSTOMERS} customers..."); customers=gen_customers(NUM_CUSTOMERS)
    print(f"Generating {NUM_SELLERS} sellers..."); sellers=gen_sellers(NUM_SELLERS)
    print(f"Generating {NUM_PRODUCTS} products..."); products=gen_products(NUM_PRODUCTS,sellers)
    print(f"Generating {NUM_ORDERS} orders..."); orders=gen_orders(NUM_ORDERS,customers,products,sellers)
    print(f"Generating {NUM_REVIEWS} reviews..."); reviews=gen_reviews(NUM_REVIEWS,orders,products)
    data={"customers":customers,"sellers":sellers,"products":products,"orders":orders,"reviews":reviews}
    tr=sum(o["total"] for o in orders); ao=tr/len(orders) if orders else 0
    print(f"\n{'─'*60}\n  Customers:       {len(customers):>6,}\n  Sellers:         {len(sellers):>6,}\n  Products:        {len(products):>6,}\n  Orders:          {len(orders):>6,}\n  Reviews:         {len(reviews):>6,}\n  Total Revenue:   €{tr:>12,.2f}\n  Avg Order Value: €{ao:>12,.2f}\n  Countries:       {len(COUNTRIES):>6}\n  Categories:      {len(CATEGORIES):>6}\n{'─'*60}")
    print(f"\nExporting JSON -> {args.output_dir}"); export_json(data,args.output_dir)
    if not args.json_only: print("\nInserting into MongoDB..."); insert_mongo(data,args.uri,args.db,args.drop)
    print("\nDone!")

if __name__=="__main__": main()
