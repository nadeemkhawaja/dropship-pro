"""
Auto Scanner — finds profitable dropship products automatically.
Scout Mode  : eBay-only, fast — returns eBay sold data for selected categories
Full Mode   : eBay + Amazon — cross-checks price, similarity, profit margin

Filter pipeline (both modes):
  1. Blocks branded / prohibited / refurbished items
  2. Uses avg_sold × 0.95 as the consistent sell price
Full mode extras:
  3. Amazon title similarity (Jaccard, min 28 %)
  4. Conflicting product-type rejection
  5. Profit threshold gate
  6. Returns match confidence score
"""
import asyncio, re, logging, json, urllib.parse
from typing import Optional
from services.ebay_api import eBayClient
from services.amazon_scraper import search as amz_search, fetch_product as amz_fetch
from services.database import get_setting

log = logging.getLogger("AutoScanner")

# ── Blocked brands ─────────────────────────────────────────────
BLOCKED_BRANDS = {
    "apple","iphone","ipad","macbook","airpods","samsung","galaxy",
    "google","pixel","sony","bose","anker","govee","philips","hue",
    "amazon","echo","alexa","kindle","ring","nest","dyson","shark",
    "ninja","instant pot","keurig","nespresso","dewalt","milwaukee",
    "makita","bosch","lg","dell","hp","lenovo","asus","acer","microsoft",
    "surface","xbox","playstation","nintendo","switch","lego","barbie",
    "disney","nike","adidas","under armour","north face","yeti","stanley",
    "hydro flask","cuisinart","kitchenaid","roomba","irobot","fitbit",
    "garmin","logitech","razer","corsair","western digital","seagate",
    "iottie","belkin","mophie","otterbox","spigen","ugreen","baseus",
    "aukey","ravpower","jackery","bluetti","olight","streamlight",
    "gerber","leatherman","victorinox","benchmade","spyderco",
}

# ── Prohibited keywords ────────────────────────────────────────
PROHIBITED_KEYWORDS = {
    "wine","beer","whiskey","bourbon","vodka","tequila","rum","gin",
    "alcohol","liquor","tobacco","cigarette","cigar","vape","e-cig",
    "adult","xxx","sexual","erotic",
    "gun","firearm","pistol","rifle","ammunition","ammo","silencer",
    "switchblade","brass knuckle","taser","stun gun",
    "cbd","thc","marijuana","cannabis","kratom","supplement claim",
    "cure","treat disease","fda approved",
    "explosive","firework","aerosol spray can",
    "live animal","fresh food","raw meat","perishable",
    "replica","counterfeit","fake","knockoff","unauthorized",
}

# ── eBay numeric category IDs (needed for Browse API seller search) ────────
EBAY_CAT_IDS = {
    "electronics":   "58058",   # Consumer Electronics
    "apparel":       "11450",   # Clothing, Shoes & Accessories
    "auto":          "6028",    # Auto Parts & Accessories
    "jewelry":       "281",     # Jewelry & Watches
    "collectibles":  "1",       # Collectibles
    "health_beauty": "26395",   # Health & Beauty
    "home_garden":   "11700",   # Home & Garden
    "kitchen":       "20625",   # Kitchen, Dining & Bar
    "pets":          "1281",    # Pet Supplies
    "office":        "316",     # Office Products & Supplies
    "sports":        "888",     # Sporting Goods
    "toys":          "220",     # Toys & Hobbies
    "baby":          "2984",    # Baby
    "outdoor":       "20710",   # Camping & Hiking / Outdoor Recreation
}

# ── 14 product categories with keywords ───────────────────────
CATEGORIES = {
    "electronics": {
        "icon": "📱",
        "label": "Electronics & Gadgets",
        "keywords": [
            "wireless earbuds true wireless stereo",
            "bluetooth earbuds noise canceling",
            "portable power bank fast charging",
            "USB C multiport hub adapter",
            "LED strip lights room decor",
            "smart plug wifi voice control",
            "wireless phone charger pad fast",
            "USB C charging cable braided",
            "retractable USB C cable fast",
            "20000mAh power bank portable charger",
            "ring light tripod selfie stand",
            "blue light blocking glasses computer",
            "bluetooth speaker portable waterproof",
            "mini projector portable home theater",
            "fitness tracker smart watch band",
            "smart watch health monitor sport",
            "security camera wifi indoor outdoor",
            "smart LED bulb color changing",
            "OBD2 scanner diagnostic code reader",
            "dash cam front rear 1080p",
            "wireless keyboard mouse combo compact",
            "USB hub 4 port charging",
            "phone screen protector tempered glass",
            "cable management clips desk wire",
            "laptop cooling pad stand fan",
            "monitor light bar desk lamp",
            "wireless charging dock station multi",
            "earphone wire headphone splitter cable",
            "digital alarm clock LED bedside",
            "magnetic phone car mount holder",
            "mini fan USB desk portable",
            "LED desk lamp dimmer touch",
            "keyboard mechanical wired compact TKL",
            "gaming headset microphone stereo wired",
            "solar power bank charger outdoor",
            "type C wall charger block fast",
            "smart home security camera indoor",
            "action camera waterproof wide angle",
            "bluetooth transmitter receiver stereo audio",
            "night vision baby monitor wifi",
        ],
    },
    "apparel": {
        "icon": "👜",
        "label": "Apparel & Accessories",
        "keywords": [
            "compression socks women men running",
            "athletic leggings high waist women",
            "quick dry running shorts men",
            "beanie hat winter knit unisex",
            "baseball cap adjustable dad hat",
            "bucket hat sun protection unisex",
            "tote bag canvas large reusable",
            "crossbody bag small strap women",
            "fanny pack waist bag travel",
            "hair scrunchie velvet set women",
            "silicone watch band replacement strap",
            "sunglasses polarized UV400 unisex",
            "athletic crew socks cushioned sport",
            "face mask reusable washable breathable",
            "winter gloves touch screen thermal",
            "neck gaiter tube scarf outdoor",
            "workout headband sweat wicking women",
            "drawstring bag backpack gym sport",
            "phone wallet case card holder",
            "loungewear set matching sweatsuit women",
            "hoodie sweatshirt pullover fleece unisex",
            "cargo shorts lightweight men summer",
            "tank top racerback women workout",
            "zip up hoodie fleece lightweight",
            "yoga pants pocket high waist",
            "oversized t shirt women graphic",
            "knit cardigan open front women",
            "bikini set two piece swimwear",
            "rash guard swimwear UV protection",
            "hair clip claw jaw set",
            "silk pillowcase standard smooth hair",
            "trucker hat mesh back snapback",
            "flip flops sandals comfort slides",
            "slip on sneakers lightweight women",
            "ankle socks low cut women",
            "beret hat wool felt women",
            "scrunchie hair tie set girls",
            "reusable shopping bag fold tote",
            "wristlet clutch wallet women zipper",
            "belt leather woven braided unisex",
        ],
    },
    "auto": {
        "icon": "🚗",
        "label": "Auto & Car Accessories",
        "keywords": [
            "car phone mount dashboard vent",
            "windshield phone holder mount car",
            "car seat gap filler console organizer",
            "trunk organizer collapsible storage car",
            "steering wheel cover faux leather",
            "windshield sun shade folding reflective",
            "car back seat organizer pocket",
            "LED interior car strip lights",
            "tire pressure gauge digital pencil",
            "car trash can hanging bin",
            "seat cover front waterproof universal",
            "all weather floor mats heavy duty",
            "car air freshener vent clip",
            "OBD2 bluetooth scanner diagnostic car",
            "jump starter portable compact car",
            "car vacuum cleaner handheld cordless",
            "dash cam 1080p wide angle front",
            "backup camera rear view wireless",
            "blind spot mirror wide angle car",
            "car cup holder expander insert",
            "trunk cargo liner mat waterproof",
            "car door handle protector cover scratch",
            "headrest hook hanger backseat car",
            "car key organizer leather holder",
            "parking sensor reverse backup alarm",
            "car sun visor extender shield",
            "emergency roadside kit car safety",
            "car wash microfiber towel detailing",
            "squeegee water blade windshield car",
            "ceramic coating spray car paint protection",
            "car wax polish compound scratch remover",
            "ice scraper snow brush car",
            "car battery tester voltage meter",
            "license plate frame stainless steel",
            "car charger dual port USB fast",
            "steering wheel phone holder magnetic",
            "anti-slip dashboard mat sticky pad",
            "seat belt adjuster shoulder strap comfort",
            "car door step ladder assist handle",
            "portable air compressor tire inflator car",
        ],
    },
    "jewelry": {
        "icon": "💎",
        "label": "Jewelry & Watches",
        "keywords": [
            "minimalist ring stainless steel women",
            "crystal stud earrings silver women",
            "layered chain necklace gold dainty",
            "charm bracelet adjustable bead women",
            "birthstone pendant necklace silver",
            "hoop earrings gold plated small",
            "anklet chain gold silver women",
            "tennis bracelet cubic zirconia silver",
            "cuff bangle bracelet stainless steel",
            "pendant necklace heart dainty women",
            "huggie hoop earrings small gold",
            "fashion watch analog women minimalist",
            "men stainless steel watch sport",
            "digital sport watch waterproof men",
            "iced out watch men hip hop",
            "skeleton watch mechanical gear men",
            "watch band replacement metal mesh",
            "silicone sport watch band 20mm",
            "set earrings rings necklace women",
            "turquoise stone bead stretch bracelet",
            "cross pendant necklace silver men",
            "evil eye bracelet protection charm",
            "pearl earrings drop dangle women",
            "moon star necklace layered women",
            "statement earrings geometric dangle drop",
            "nose ring stud hoop surgical steel",
            "cartilage ear cuff clip on",
            "men leather bracelet woven wrap",
            "signet ring stainless steel men",
            "initial letter necklace gold women",
            "tree of life pendant necklace",
            "infinity knot ring gold women",
            "feather earrings boho dangle drop",
            "men ring band stainless steel",
            "vintage style cameo brooch pin",
            "choker necklace velvet ribbon women",
            "butterfly earrings stud gold women",
            "fashion bangle bracelet set colorful",
            "ear stud set sterling silver",
            "men dog tag chain necklace",
        ],
    },
    "collectibles": {
        "icon": "🎨",
        "label": "Collectibles & Crafts",
        "keywords": [
            "diamond painting kit adults landscape",
            "paint by number canvas adults set",
            "cross stitch kit flowers beginner",
            "resin mold silicone DIY craft",
            "UV resin kit jewelry making",
            "washi tape set decorative patterned",
            "journaling sticker book aesthetic set",
            "calligraphy brush pen lettering set",
            "enamel pin set aesthetic cute",
            "pressed flower kit craft dried",
            "macrame cord natural cotton rope",
            "embroidery kit beginner floral hoop",
            "candle making kit soy wax",
            "soap making kit melt pour",
            "polymer clay sculpting kit set",
            "sketch book drawing pad artist",
            "watercolor paint set portable artist",
            "acrylic paint set artist canvas",
            "colored pencil set professional artist",
            "alcohol ink art set resin",
            "linocut printmaking carving block kit",
            "cricut vinyl rolls set assorted",
            "foam clay lightweight modeling craft",
            "resin pigment powder mica set",
            "bookbinding kit leather journal making",
            "needle felting kit beginner set",
            "friendship bracelet string thread kit",
            "bead kit jewelry making assorted",
            "art journal mixed media sketchbook",
            "5D diamond art kit full drill",
            "sticker paper printable holographic sheet",
            "bullet journal dot grid notebook",
            "ink stamp pad set archival",
            "paper quilling kit strips tool",
            "origami paper set colored folding",
            "glitter craft set fine ultra",
            "paint pouring kit acrylic cells",
            "shrink plastic film art craft",
            "air dry clay sculpting set",
            "scrapbook kit album memory set",
        ],
    },
    "health_beauty": {
        "icon": "💊",
        "label": "Health & Beauty",
        "keywords": [
            "jade roller face massager set",
            "gua sha stone facial scraper",
            "ice roller face neck puffiness",
            "LED light therapy face mask",
            "electric scalp massager hair growth",
            "under eye patches collagen hydrogel",
            "pimple patch acne spot treatment",
            "silicone face cleansing brush gentle",
            "derma roller 0.25mm microneedle face",
            "lash lift kit perming eyelash",
            "magnetic eyelashes reusable no glue",
            "teeth whitening strips professional grade",
            "facial steamer nano mist open pores",
            "blackhead remover vacuum pore cleanser",
            "massage gun percussion deep tissue",
            "foot file callus remover electric",
            "nail art kit gel stamping set",
            "cuticle oil pen nourishing nail",
            "eyebrow stencil shaping kit reusable",
            "sleep mask contoured 3D eye",
            "hair growth oil serum scalp",
            "argan oil hair serum frizz",
            "vitamin C serum face brightening",
            "hyaluronic acid serum face moisturizing",
            "retinol cream anti aging wrinkle",
            "charcoal face mask peel off",
            "sheet mask set Korean skincare",
            "acupressure massage slippers reflexology",
            "resistance band set booty workout",
            "posture corrector back brace support",
            "heating pad back neck electric",
            "knee brace compression support pain",
            "back massager shiatsu electric pillow",
            "oral irrigator water flosser cordless",
            "electric toothbrush replacement head set",
            "eyelash curler heated lash tool",
            "hair removal epilator electric women",
            "body scrub exfoliating brush shower",
            "bamboo charcoal soap bar natural",
            "makeup brush set synthetic full",
        ],
    },
    "home_garden": {
        "icon": "🏠",
        "label": "Home & Garden",
        "keywords": [
            "floating wall shelf wooden bracket",
            "succulent pot ceramic small planter",
            "solar garden light stake path",
            "shower curtain rings rust proof",
            "drawer organizer dividers set adjustable",
            "throw pillow cover 18x18 decorative",
            "picture frame collage wall set",
            "under bed storage bag organizer",
            "hanging plant pot macrame holder",
            "door stopper floor heavy duty",
            "self-watering planter indoor herb",
            "hydroponics growing kit indoor herb",
            "vertical wall planter pocket garden",
            "raised garden bed fabric planter",
            "garden gloves grip breathable women",
            "compost bin kitchen countertop odor free",
            "vegetable grow bag fabric root pouch",
            "drip irrigation kit garden watering",
            "LED grow light indoor plant",
            "string lights outdoor patio waterproof",
            "candle holder set glass decorative",
            "wax melt warmer electric scented",
            "artificial succulent plant pot fake",
            "doormat outdoor entrance non-slip rubber",
            "window insulation film clear thermal",
            "over door hook organizer rack",
            "tension rod closet cabinet divider",
            "stackable storage bin cubby organizer",
            "wall command hook adhesive strip",
            "closet organizer velvet hanger set",
            "laundry hamper collapsible large handle",
            "ironing board cover replacement pad",
            "mop spray flat microfiber floor",
            "squeegee window cleaning extendable pole",
            "broom dustpan set upright standing",
            "toilet bowl brush set holder",
            "shower caddy organizer rust proof",
            "bath mat non-slip quick dry",
            "toilet paper holder stand freestanding",
            "wall mounted towel ring bar",
        ],
    },
    "kitchen": {
        "icon": "🍳",
        "label": "Kitchen & Dining",
        "keywords": [
            "silicone kitchen utensil set cooking",
            "spice rack organizer rotating turntable",
            "reusable beeswax food wrap set",
            "magnetic knife strip wall mounted",
            "garlic press stainless steel rocker",
            "egg cooker electric rapid poacher",
            "salad spinner bowl large colander",
            "coffee pour over dripper set",
            "French press coffee maker glass",
            "electric kettle glass gooseneck pour",
            "air fryer basket liner parchment",
            "cast iron skillet pre-seasoned heavy",
            "vegetable chopper dicer slicer multi",
            "mandoline slicer vegetable adjustable blade",
            "can opener electric automatic smooth",
            "avocado slicer pitter tool 3-in-1",
            "silicone stretch food storage lids",
            "vacuum seal food storage bags",
            "reusable produce mesh bag set",
            "kitchen timer digital magnetic loud",
            "dish drying rack compact stainless",
            "over sink colander strainer expandable",
            "cutting board bamboo large set",
            "measuring cups spoons set stainless",
            "mixing bowl set nesting stainless",
            "pot lid organizer rack holder",
            "pan rack organizer vertical cabinet",
            "splatter screen guard grease stopper",
            "kitchen scale digital food grams",
            "wine aerator pourer decanter stopper",
            "cheese grater box microplane stainless",
            "apple corer peeler spiralizer tool",
            "cookie scoop set baking stainless",
            "pastry bag set cake decorating tips",
            "silicone mold ice cube tray large",
            "portable blender USB rechargeable smoothie",
            "mini waffle maker compact non-stick",
            "breakfast sandwich maker compact electric",
            "sous vide clip vacuum bag set",
            "bottle brush set cleaning long handle",
        ],
    },
    "pets": {
        "icon": "🐾",
        "label": "Pet Supplies",
        "keywords": [
            "dog slow feeder bowl puzzle",
            "cat tunnel play interactive foldable",
            "pet hair remover roller reusable",
            "cat window perch suction cup",
            "dog paw cleaner portable cup",
            "cat scratcher cardboard lounge pad",
            "dog treat pouch training clip",
            "no-pull dog harness breathable vest",
            "retractable dog leash lock brake",
            "dog collar reflective adjustable nylon",
            "pet grooming glove deshedding brush",
            "cat water fountain electric filter",
            "dog cooling mat pressure activated",
            "pet blanket soft fleece warm",
            "automatic laser cat toy interactive",
            "dog chew toy indestructible rubber",
            "pet carrier bag airline approved",
            "cat tree tower condo scratching post",
            "dog bandana set snap button",
            "LED dog collar light up safety",
            "dog booties shoes winter snow paw",
            "puppy playpen exercise pen foldable",
            "dog ramp stairs car couch",
            "cat litter mat trapper waterproof",
            "self-cleaning slicker brush deshedding dog",
            "dog puzzle toy food dispensing",
            "pet first aid kit emergency travel",
            "dog anxiety wrap thunder shirt",
            "cat feather wand teaser toy",
            "elevated dog bowl stand stainless",
            "pet nail grinder trimmer quiet",
            "dog seat belt harness car safety",
            "outdoor dog water bottle travel",
            "fish tank decoration coral reef",
            "hamster wheel silent spinner cage",
            "bird mirror bell perch toy",
            "dog birthday party hat set",
            "biodegradable dog poop bags rolls",
            "flea collar tick prevention dogs",
            "pet stroller jogger cat dog",
        ],
    },
    "office": {
        "icon": "💼",
        "label": "Office & Desk",
        "keywords": [
            "desk organizer bamboo pen holder set",
            "laptop stand adjustable aluminum portable",
            "extended mouse pad desk mat large",
            "cable management box cord organizer",
            "monitor riser stand drawer storage",
            "mesh desk organizer file tray",
            "sticky notes dispenser pop up cube",
            "document letter tray stackable black",
            "standing desk converter sit stand",
            "ergonomic wrist rest keyboard pad",
            "adjustable phone stand aluminum desktop",
            "ring light clip laptop monitor",
            "USB desk fan silent compact",
            "USB mini humidifier desk personal",
            "thermal label printer wireless compact",
            "label maker tape refill set",
            "dry erase calendar whiteboard desktop",
            "magnetic dry erase board wall",
            "cork board pin board bulletin",
            "pen pencil cup holder weighted",
            "book ends heavy duty metal set",
            "drawer organizer insert set adjustable",
            "binder clip set assorted large",
            "stapler heavy duty desktop full strip",
            "hole punch 3-ring desktop metal",
            "tape dispenser weighted non-skid",
            "wireless charger desk pad leather",
            "webcam 1080p HD autofocus streaming",
            "microphone USB cardioid desk podcast",
            "ergonomic footrest under desk adjustable",
            "seat cushion memory foam coccyx",
            "lumbar support pillow office chair",
            "whiteboard markers set dry erase",
            "push pin map tacks set",
            "file folder expanding accordion portable",
            "notebook spiral hardcover ruled journal",
            "planner weekly monthly undated desk",
            "pencil case zipper pouch large",
            "mechanical pencil set refill lead",
            "page flag sticky tab index set",
        ],
    },
    "sports": {
        "icon": "💪",
        "label": "Sports & Fitness",
        "keywords": [
            "resistance bands set loop fabric",
            "foam roller deep tissue massage",
            "jump rope speed cable bearing adult",
            "workout gloves weightlifting grip wrist",
            "ab wheel roller core exercise",
            "knee brace compression sleeve support",
            "yoga mat thick non-slip alignment",
            "insulated water bottle stainless steel",
            "pull up bar doorway no screw",
            "push up bars handles rotating",
            "adjustable dumbbell set home gym",
            "kettlebell cast iron adjustable handle",
            "weight lifting belt support back",
            "running waist pack belt hydration",
            "gym bag duffel wet dry",
            "boxing gloves training sparring adult",
            "hand wraps boxing 180 inch",
            "battle rope training anchor set",
            "agility ladder cones speed training",
            "balance board wobble disc core",
            "suspension trainer strap bodyweight system",
            "tennis elbow brace compression strap",
            "ankle brace lace-up support sprain",
            "massage ball trigger point rolling",
            "stretching strap yoga flexibility band",
            "swim goggles anti-fog UV protection",
            "swim cap silicone waterproof adult",
            "cycling gloves half finger padded",
            "bike phone mount handlebar holder",
            "sweat headband elastic wicking sport",
            "cooling towel instant snap sport",
            "sport armband phone holder running",
            "fitness tracker calorie step counter",
            # ── Racket & ball sports ───────────────────
            "pickleball paddle set beginner lightweight",
            "pickleball balls outdoor indoor set",
            "badminton racket set backyard outdoor",
            "badminton shuttlecock feather nylon set",
            "ping pong paddle set table tennis",
            "ping pong balls table tennis set",
            "tennis ball can training extra duty",
            "soccer ball size 5 training outdoor",
            "basketball outdoor indoor rubber grip",
            "volleyball official size indoor outdoor",
            "football training grip composite leather",
            "baseball glove youth adult fielding",
            "golf practice balls foam indoor",
            "lacrosse ball set training rubber",
            "racquetball set goggles balls court",
            "cornhole bags set replacement outdoor",
            "bocce ball set resin outdoor",
        ],
    },
    "toys": {
        "icon": "🧸",
        "label": "Toys & Hobbies",
        "keywords": [
            "fidget cube stress relief desk toy",
            "magnetic tiles building blocks kids",
            "slime kit glitter fluffy making DIY",
            "flying orb ball hover boomerang",
            "mini drone kids beginner indoor",
            "kinetic sand set mold kids",
            "foam blaster dart gun refill",
            "pop it fidget toy bubble kids",
            "squishy slow rise mochi toy",
            "card game family party adults",
            "jigsaw puzzle 1000 piece adults",
            "paint by number watercolor kids set",
            "kids karaoke microphone bluetooth speaker",
            "walkie talkie set kids outdoor",
            "educational digital microscope kids portable",
            "marble run track set kids",
            "wooden puzzle shape sorter toddler",
            "sensory bin filler kinetic sand",
            "bath bomb kit making kids DIY",
            "grow crystal kit science experiment",
            "volcano science kit experiment kids",
            "sticker book activity kids reusable",
            "color changing slime kit kids",
            "rocket launcher outdoor foam kids",
            "glow in dark stars ceiling kit",
            "garden grow kit seed children",
            "miniature dollhouse furniture set DIY",
            "remote control car off road",
            "foam glider plane launcher outdoor",
            "water balloon bunch quick fill",
            "bubble machine gun wand refill",
            "magic trick set beginner kids",
            "finger puppet set animals storytelling",
            "play dough tool accessory set",
            "robot building kit STEM coding",
            "solar system model kit educational",
            "chess set beginners magnetic travel",
            "Jenga stacking tumble tower game",
            "sandbox mold beach sand toy",
            "kids safety scissors craft set",
        ],
    },
    "baby": {
        "icon": "👶",
        "label": "Baby & Kids",
        "keywords": [
            "silicone teething toy baby chew",
            "toddler sippy cup spill proof",
            "kids toy bin storage organizer",
            "star projector night light nursery",
            "diaper bag backpack large capacity",
            "potty training seat toddler insert",
            "baby bath toy floating squirt",
            "kids lunch box insulated bento",
            "swaddle blanket muslin cotton infant",
            "baby sound machine white noise",
            "silicone baby bib waterproof pocket",
            "baby nasal aspirator electric snot",
            "baby bottle anti-colic BPA free",
            "breast milk storage bag set",
            "baby monitor video wifi HD",
            "infant car seat stroller travel system",
            "baby carrier wrap ergonomic newborn",
            "baby bouncer rocker vibration seat",
            "play mat gym activity infant",
            "stroller fan portable USB clip",
            "baby food maker steamer blender",
            "silicone feeding set toddler suction",
            "kids water bottle straw leakproof",
            "toddler backpack small kindergarten girls",
            "kids rain boots rubber waterproof",
            "children sunglasses UV400 flexible rubber",
            "kids swimming arm floaties inflatable",
            "baby gate pressure mount adjustable",
            "crib mobile musical hanging nursery",
            "toddler pillow set washable cotton",
            "baby wipe warmer electric dispenser",
            "kids first aid kit travel",
            "toddler utensil set fork spoon",
            "bath kneeler elbow pad set",
            "baby towel hooded animal soft",
            "kids art smock waterproof sleeves",
            "magnetic drawing board kids erase",
            "kids puzzle foam floor mat",
            "baby rattle shaker set newborn",
            "children rain poncho reusable foldable",
        ],
    },
    "outdoor": {
        "icon": "🌿",
        "label": "Outdoor & Recreation",
        "keywords": [
            "camping lantern LED rechargeable solar",
            "trekking poles collapsible lightweight hiking",
            "hammock camping portable nylon lightweight",
            "waterproof dry bag roll top",
            "carabiner locking clip hook set",
            "tactical flashlight high lumen rechargeable",
            "camping stove portable backpacking butane",
            "water filter straw purifier hiking",
            "sleeping bag lightweight compact camping",
            "camp pillow compressible inflatable travel",
            "tent footprint tarp ground cloth",
            "camp chair folding lightweight compact",
            "headlamp rechargeable USB trail running",
            "multitool pocket knife pliers stainless",
            "fire starter waterproof ferro rod",
            "paracord bracelet 550 survival fire",
            "emergency mylar blanket compact survival",
            "bear canister food storage camping",
            "insect repellent bracelet wristband natural",
            "hiking gaiters waterproof trail protection",
            "trekking socks merino wool cushioned",
            "hydration backpack bladder reservoir trail",
            "fishing rod portable telescopic travel",
            "fishing tackle box set lure",
            "snorkeling set mask fin adult",
            "paddle board fin leash set",
            "kayak paddle lightweight carbon fiber",
            "beach umbrella sand anchor anchor",
            "beach tent sun shelter UV pop up",
            "outdoor blanket waterproof picnic fleece",
            "binoculars compact zoom bird watching",
            "compass navigation waterproof orienteering",
            "solar phone charger panel portable",
            "camp cooking set mess kit",
            "hammock strap suspension kit heavy",
            "rock climbing chalk bag grip",
            "ski gloves waterproof touchscreen winter",
            "snow shovel folding collapsible portable",
            "kite dual line stunt sport",
            "frisbee disc sport ultimate outdoor",
        ],
    },
}

# ── Liquid / Food / Hazard blocklist ──────────────────────────
LIQUID_FOOD_HAZARD = {
    # Liquids & topicals
    "lotion","serum","toner","essence","mist","cologne","perfume",
    "fragrance","shampoo","conditioner","body wash","face wash",
    "cleanser","moisturizer","sunscreen","lip gloss","lip balm",
    "nail polish","hair dye","hair color","bleach","solution","fluid",
    "liquid soap","hand soap","dish soap","wax melt","candle wax",
    # Food / edible
    "food","snack","candy","chocolate","coffee","tea","gummy",
    "vitamin","supplement","protein powder","nuts","dried fruit",
    "sauce","seasoning","spice","cooking oil","butter","juice",
    "drink","beverage","edible","flavoring","sweetener",
    # Hazards
    "pesticide","herbicide","insecticide","flammable","corrosive",
    "battery acid","drain cleaner","rodenticide",
}

# ── Legacy flat list — kept for backward compatibility
SCAN_CATEGORIES = [kw for cat in CATEGORIES.values() for kw in cat["keywords"]]

# ── Stop words ─────────────────────────────────────────────────
STOP_WORDS = {
    "for","the","a","an","in","of","with","and","or","to","on","at","by",
    "from","is","it","its","are","be","this","that","was","as","has","have",
    "had","not","but","so","if","do","did","can","will","may","new","get",
    "use","2pcs","3pcs","4pcs","2pack","3pack","pack","pcs","piece","lot",
    "usa","fast","free","ship","brand","item","great","best","top","high",
    "quality","super","ultra","pro","mini","max","plus","premium","x2","x3",
}

# ── Conflicting product-type pairs ─────────────────────────────
CONFLICTING_PAIRS = [
    ({"strip","strips","bar","bars","tape","ribbon","linear","panel"},
     {"puck","disc","round","circular","dome","bulb","ball","sphere"}),
    ({"wired","corded","3.5mm","aux","cable"},
     {"wireless","bluetooth","wifi","wi-fi","true wireless","tws"}),
    ({"glasses","spectacles","eyewear","frames"},
     {"goggles","visor","shield","mask"}),
    ({"floor","standing","freestanding"},
     {"desk","desktop","tabletop","clamp","clip"}),
]


# ── Filter helpers ─────────────────────────────────────────────

def is_branded(title: str) -> bool:
    title_lower = title.lower()
    for brand in BLOCKED_BRANDS:
        if re.search(r'\b' + re.escape(brand) + r'\b', title_lower):
            return True
    return False


def is_prohibited(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in PROHIBITED_KEYWORDS)


def is_liquid_food_hazard(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in LIQUID_FOOD_HAZARD)


def is_refurbished(title: str) -> bool:
    bad = ["refurbished","refurb","used","pre-owned","preowned",
           "open box","open-box","parts only","for parts","damaged",
           "broken","as is","as-is","salvage","read description"]
    return any(b in title.lower() for b in bad)


def passes_filters(title: str) -> tuple[bool, str]:
    if not title or len(title) < 5:
        return False, "no title"
    if is_branded(title):
        return False, "branded product"
    if is_prohibited(title):
        return False, "prohibited category"
    if is_refurbished(title):
        return False, "refurbished/used"
    return True, "ok"


# ── Title similarity ───────────────────────────────────────────

def _tokenize(title: str) -> set:
    words = re.findall(r'\b[a-z0-9]+\b', title.lower())
    return {w for w in words if len(w) > 2 and w not in STOP_WORDS}


def title_similarity(ebay_title: str, amazon_title: str) -> int:
    """Jaccard similarity on meaningful words. Returns 0–100."""
    t1 = _tokenize(ebay_title)
    t2 = _tokenize(amazon_title)
    if not t1 or not t2:
        return 0
    union = len(t1 | t2)
    if union == 0:
        return 0
    return round(len(t1 & t2) / union * 100)


def has_conflicting_types(ebay_title: str, amazon_title: str) -> bool:
    e = ebay_title.lower()
    a = amazon_title.lower()
    for group_a, group_b in CONFLICTING_PAIRS:
        e_in_a = any(w in e for w in group_a)
        a_in_b = any(w in a for w in group_b)
        e_in_b = any(w in e for w in group_b)
        a_in_a = any(w in a for w in group_a)
        if e_in_a and a_in_b:
            return True
        if e_in_b and a_in_a:
            return True
    return False


def match_label(score: int) -> str:
    if score >= 60:
        return "great"
    if score >= 40:
        return "good"
    return "weak"


# ── Profit calculator ──────────────────────────────────────────

def calc_profit(amazon_cost: float, ebay_sell: float,
                ebay_fee_pct: float = 13.0, payment_fee_pct: float = 3.0,
                min_profit: float = 5.0) -> dict:
    total_fee_pct = ebay_fee_pct + payment_fee_pct
    fees   = round(ebay_sell * total_fee_pct / 100, 2)
    profit = round(ebay_sell - amazon_cost - fees, 2)
    roi    = round(profit / amazon_cost * 100, 1) if amazon_cost > 0 else 0
    return {
        "amazon_cost":  amazon_cost,
        "ebay_sell":    ebay_sell,
        "fees":         fees,
        "net_profit":   profit,
        "roi_pct":      roi,
        "profitable":   profit >= min_profit,
    }


# ── Amazon matcher ─────────────────────────────────────────────

async def find_amazon_match(ebay_title: str, max_cost: float) -> Optional[dict]:
    clean = re.sub(
        r'\b(new|fast|free|ship|usa|lot|pack|set|pcs|pc|brand|'
        r'seller|quality|wholesale|bulk|quantity|listing)\b',
        '', ebay_title, flags=re.I
    ).strip()
    clean = re.sub(r'\s+', ' ', clean).strip()[:60]

    try:
        results = await amz_search(clean, max_results=5)  # 5 is enough; fewer = faster
        await asyncio.sleep(0.3)

        scored = []
        for r in results:
            cost = r.get("source_price")
            if not cost or cost <= 0:
                continue
            if cost >= max_cost:
                continue
            amz_title = r.get("title", "")
            ok, _ = passes_filters(amz_title)
            if not ok:
                continue
            if has_conflicting_types(ebay_title, amz_title):
                log.debug(f"Type conflict: '{ebay_title[:40]}' ≠ '{amz_title[:40]}'")
                continue
            sim = title_similarity(ebay_title, amz_title)
            if sim < 28:
                log.debug(f"Low sim {sim}%: '{ebay_title[:40]}' ≠ '{amz_title[:40]}'")
                continue
            scored.append((sim, cost, r))

        if not scored:
            return None

        scored.sort(key=lambda x: (-x[0], x[1]))
        best_sim, _, best = scored[0]
        best["_match_score"] = best_sim
        return best

    except Exception as e:
        log.error(f"Amazon match error for '{ebay_title[:40]}': {e}")
        return None


# ── Top Sellers discovery ──────────────────────────────────────

async def top_sellers_scan(
    ebay_client: eBayClient,
    category_id: str,
    max_products: int = 200,
) -> list:
    """
    Find top-selling BIN products ($5–$50) in a category.

    Method (same as AutoDS):
      - Search eBay category with sort=bestMatch — eBay ranks by purchase
        activity so top results = highest-demand products
      - Extract seller usernames from results to identify top sellers
      - Filter out branded, prohibited, food/liquid/hazard items
      - Return products grouped/sorted by seller frequency (top sellers first)
    """
    ebay_cat_id = EBAY_CAT_IDS.get(category_id)
    if not ebay_cat_id:
        log.warning(f"top_sellers_scan: unknown category {category_id}")
        return []

    result = await ebay_client.search_category_best(ebay_cat_id, limit=200)
    items  = result.get("items", [])
    log.info(f"top_sellers_scan [{category_id}]: {len(items)} raw results from eBay")

    # ── Filter ────────────────────────────────────────────────────
    clean   = []
    seen    = set()
    seller_counts: dict = {}

    for item in items:
        price = item.get("price")
        if price is None or not (5.0 <= float(price) <= 50.0):
            continue
        title = item.get("title", "")
        if not title:
            continue
        if (is_branded(title) or is_prohibited(title)
                or is_refurbished(title) or is_liquid_food_hazard(title)):
            continue
        # Soft dedup — skip near-identical titles
        key = title.lower()[:45]
        if key in seen:
            continue
        seen.add(key)

        seller = item.get("seller") or "unknown"
        seller_counts[seller] = seller_counts.get(seller, 0) + 1
        clean.append(item)

    log.info(f"top_sellers_scan [{category_id}]: {len(clean)} products after filter, "
             f"{len(seller_counts)} unique sellers")

    # ── Attach seller rank & sort ─────────────────────────────────
    for p in clean:
        p["seller_product_count"] = seller_counts.get(p.get("seller") or "unknown", 0)

    # Sort: sellers with most products in top-200 appear first (they are the top sellers)
    # Within same seller, preserve bestMatch order (original list order)
    clean.sort(key=lambda x: x["seller_product_count"], reverse=True)

    return clean[:max_products]


# ── eBay Scout (fast, eBay-only) ───────────────────────────────

async def scout_keyword(ebay_client: eBayClient, keywords: str) -> list:
    """
    Enhanced eBay-only scout scan for one keyword set.
    Runs sold + active searches concurrently (same API, no extra cost).
    Returns up to MAX_PER_KW deduplicated listings with full market stats.
    """
    MAX_PER_KW = 3   # max distinct results per keyword set

    results         = []
    kept_token_sets = []

    try:
        # ── Run sold + active searches at the same time ────────────
        sold, active = await asyncio.gather(
            ebay_client.search_sold(keywords, limit=50),
            ebay_client.search_active(keywords, limit=5),   # only need .total
        )

        items      = sold.get("items", [])
        avg_sold   = sold.get("avg_price")
        total_sold = sold.get("total", 0)        # total sold on all of eBay
        active_cnt = active.get("total", 0)      # total active listings on eBay

        if not avg_sold or avg_sold < 8:
            return []

        avg_sell_price = round(avg_sold * 0.95, 2)

        # ── Market stats from 50 sold items ────────────────────────
        prices = [i["price"] for i in items if i.get("price")]
        price_min = round(min(prices), 2) if prices else avg_sold
        price_max = round(max(prices), 2) if prices else avg_sold

        sellers = [i["seller"] for i in items if i.get("seller")]
        unique_sellers = len(set(sellers))

        conds   = [i.get("condition", "").lower() for i in items]
        new_pct = round(sum(1 for c in conds if "new" in c) / len(conds) * 100) if conds else 0

        # ── Estimated profit range (no Amazon price yet) ───────────
        # Assumes Amazon costs 55–72 % of eBay sell price for unbranded generics
        # Fees = 16 % of sell price (13 % eBay + 3 % payment)
        # Pessimistic: cost = 72 % → profit = sell × (1 - 0.72 - 0.16) = sell × 0.12
        # Optimistic : cost = 55 % → profit = sell × (1 - 0.55 - 0.16) = sell × 0.29
        est_profit_low  = round(avg_sell_price * 0.12, 2)
        est_profit_high = round(avg_sell_price * 0.29, 2)
        est_roi_low     = round(est_profit_low  / (avg_sell_price * 0.72) * 100)
        est_roi_high    = round(est_profit_high / (avg_sell_price * 0.55) * 100)

        # ── Demand tier ────────────────────────────────────────────
        if   total_sold >= 500: demand = "hot"
        elif total_sold >= 100: demand = "good"
        elif total_sold >= 20:  demand = "moderate"
        else:                   demand = "low"

        # ── Competition tier ───────────────────────────────────────
        if   active_cnt < 30:  competition = "low"
        elif active_cnt < 150: competition = "medium"
        else:                  competition = "high"

        # ── Opportunity score 0–100 (higher = better) ─────────────
        demand_pts = min(50, round(total_sold / 20))      # up to 50 pts for demand
        comp_pts   = 30 if competition == "low" else 15 if competition == "medium" else 0
        new_pts    = round(new_pct / 5)                   # up to 20 pts for new %
        opp_score  = min(100, demand_pts + comp_pts + new_pts)

        # ── Pick up to MAX_PER_KW unique items ─────────────────────
        for item in items[:50]:
            if len(results) >= MAX_PER_KW:
                break

            title = item.get("title", "")
            if not title:
                continue
            ok, _ = passes_filters(title)
            if not ok:
                continue

            tokens = _tokenize(title)
            too_similar = False
            for existing in kept_token_sets:
                union = len(tokens | existing)
                if union > 0 and len(tokens & existing) / union > 0.50:
                    too_similar = True
                    break
            if too_similar:
                continue

            kept_token_sets.append(tokens)
            results.append({
                # ── Core ───────────────────────────────────────────
                "ebay_title":        title,
                "ebay_item_url":     item.get("item_url", ""),
                "ebay_search_url":   (
                    "https://www.ebay.com/sch/i.html?_nkw="
                    + urllib.parse.quote(title[:80])
                    + "&LH_Sold=1&LH_Complete=1"
                ),
                "amazon_search_url": (
                    "https://www.amazon.com/s?k="
                    + urllib.parse.quote(title[:60])
                ),
                "image":             item.get("image", ""),
                "category":          keywords,
                # ── Pricing ────────────────────────────────────────
                "ebay_avg_sold":     avg_sold,
                "ebay_sell_price":   avg_sell_price,
                "price_min":         price_min,
                "price_max":         price_max,
                # ── Market intel ───────────────────────────────────
                "total_sold":        total_sold,
                "active_listings":   active_cnt,
                "unique_sellers":    unique_sellers,
                "new_pct":           new_pct,
                "demand":            demand,
                "competition":       competition,
                "opp_score":         opp_score,
                # ── Estimated profit (rough — no Amazon data yet) ──
                "est_profit_low":    est_profit_low,
                "est_profit_high":   est_profit_high,
                "est_roi_low":       est_roi_low,
                "est_roi_high":      est_roi_high,
            })

    except Exception as e:
        log.error(f"scout_keyword '{keywords}' error: {e}")
    return results


# ── Full scan (eBay + Amazon) ──────────────────────────────────

async def scan_category(ebay_client: eBayClient, keywords: str,
                        ebay_fee_pct: float, payment_fee_pct: float,
                        min_profit: float) -> list:
    """
    Full scan — eBay sold → Amazon cross-check → profit calc.
    Uses avg_sold × 0.95 as the consistent sell price for all calcs.
    """
    opportunities = []
    try:
        sold = await ebay_client.search_sold(keywords, limit=50)
        items = sold.get("items", [])
        avg_sold = sold.get("avg_price")

        if not avg_sold or avg_sold < 10:
            return []

        avg_sell_price = round(avg_sold * 0.95, 2)

        # ── Full scan: check at most 12 eBay items against Amazon.
        # More than that risks Amazon blocking mid-scan.
        # If Amazon returns nothing 4 times in a row, it's blocked — bail early.
        consecutive_misses = 0
        MISS_LIMIT         = 4   # bail if Amazon blanks 4 items in a row
        ITEM_LIMIT         = 12  # max eBay items to check per keyword

        for item in items[:ITEM_LIMIT]:
            title = item.get("title", "")
            if not title:
                continue

            ok, reason = passes_filters(title)
            if not ok:
                log.debug(f"Filtered '{title[:40]}' — {reason}")
                continue

            amz = await find_amazon_match(title, avg_sell_price)
            if not amz:
                consecutive_misses += 1
                if consecutive_misses >= MISS_LIMIT:
                    log.warning(f"Amazon returning nothing for '{keywords[:30]}' — likely blocked. Stopping early.")
                    break
                continue
            consecutive_misses = 0  # reset on success

            amazon_cost = amz.get("source_price")
            if not amazon_cost:
                continue

            match_score = amz.get("_match_score", 0)

            profit_data = calc_profit(
                amazon_cost, avg_sell_price, ebay_fee_pct, payment_fee_pct, min_profit
            )

            if not profit_data["profitable"]:
                continue

            ebay_search_url = (
                "https://www.ebay.com/sch/i.html?_nkw="
                + urllib.parse.quote(title[:80])
                + "&LH_Sold=1&LH_Complete=1"
            )
            opportunities.append({
                "ebay_title":      title,
                "ebay_item_url":   item.get("item_url", ""),
                "ebay_search_url": ebay_search_url,
                "amazon_title":    amz.get("title", ""),
                "amazon_asin":     amz.get("source_id", ""),
                "amazon_cost":     amazon_cost,
                "amazon_url":      f"https://www.amazon.com/dp/{amz.get('source_id', '')}",
                "amazon_rating":   amz.get("rating", 0),
                "amazon_reviews":  amz.get("review_count", 0),
                "ebay_avg_sold":   avg_sold,
                "ebay_sell_price": avg_sell_price,
                "match_score":     match_score,
                "match_label":     match_label(match_score),
                "image_urls":      amz.get("image_urls", []),
                **profit_data,
                "category":        keywords,
                "filter_passed":   True,
            })
            await asyncio.sleep(0.2)

    except Exception as e:
        log.error(f"scan_category '{keywords}' error: {e}")

    return opportunities


# ── Legacy entry point ─────────────────────────────────────────

async def run_auto_scan(max_categories: int = 5,
                        category_keywords: Optional[list] = None) -> dict:
    """
    Legacy blocking scan — kept for backward compatibility.
    Prefer the background-task approach via main.py.
    """
    ebay_fee  = float(get_setting("ebay_fee_pct", "13"))
    pay_fee   = float(get_setting("payment_fee_pct", "3"))
    min_prof  = float(get_setting("min_profit_usd", "5"))

    ebay = eBayClient(
        client_id          = get_setting("ebay_client_id"),
        client_secret      = get_setting("ebay_client_secret"),
        user_refresh_token = get_setting("ebay_refresh_token"),
    )

    if not ebay.is_configured():
        return {"error": "eBay API not configured. Add keys in Settings.", "results": []}

    keywords = category_keywords or SCAN_CATEGORIES[:max_categories]
    all_opps = []
    scanned  = 0

    for kw in keywords:
        log.info(f"Scanning: {kw}")
        opps = await scan_category(ebay, kw, ebay_fee, pay_fee, min_prof)
        scanned += 1
        all_opps.extend(opps)
        await asyncio.sleep(1.0)

    seen_asins = set()
    unique = []
    for o in all_opps:
        asin = o.get("amazon_asin", "")
        if asin and asin not in seen_asins:
            seen_asins.add(asin)
            unique.append(o)

    unique.sort(key=lambda x: (-x.get("match_score", 0), -x.get("roi_pct", 0)))

    return {
        "results":            unique[:50],
        "total_found":        len(unique),
        "categories_scanned": scanned,
        "scan_complete":      True,
    }
