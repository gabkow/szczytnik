<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Szczytnik</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f4f4f4; color: #333; }
        .container { max-width: 800px; background: white; padding: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h1 { color: #0056b3; }
        .status { padding: 10px; background: #e2f0d9; border: 1px solid #b4c6e7; margin-bottom: 20px; }
    </style>
</head>
<body>

<div class="container">
    <h1>System Szczytnik</h1>
    <div class="status">
        <strong>Status połączenia z API:</strong> 
        <?php
            $api_url = 'http://backend:8000/';
            $response = @file_get_contents($api_url);
            if ($response) {
                $data = json_decode($response, true);
                echo "Połączono! Odpowiedź API: " . $data['message'];
            } else {
                echo "<span style='color:red;'>Brak połączenia z API backendu.</span>";
            }
        ?>
    </div>

    <h3>Panel główny</h3>
    <ul>
        <li><a href="#">Przeglądaj katalog artykułów</a></li>
        <li><a href="#">Wyszukiwarka AI</a></li>
        <li><a href="#">Wgraj nowe czasopismo (PDF)</a></li>
    </ul>
</div>

</body>
</html>