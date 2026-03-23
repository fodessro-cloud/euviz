use strict;
use IO::Socket::INET;

my $root = 'C:/Users/' . "\xc4\xbd" . 'ubom' . "\xc3\xad" . 'rFoga' . "\xc5\xa1" . '/Desktop/finila';
my $port = 3141;

my $server = IO::Socket::INET->new(
    LocalPort => $port,
    Listen    => 10,
    ReuseAddr => 1,
    Proto     => 'tcp',
) or die "Cannot bind port $port: $!";

print "EUViz server running at http://localhost:$port\n";
$| = 1;

while (my $client = $server->accept) {
    my $request = '';
    while (my $line = <$client>) {
        $request .= $line;
        last if $line =~ /^\r?\n$/;
    }

    my ($path) = $request =~ /^GET\s+([^\s]+)/;
    $path //= '/';
    $path =~ s/\?.*//;
    $path =~ s|//+|/|g;

    my $file = $root . $path;
    $file .= '/index.html' if -d $file;

    if (-f $file) {
        open my $fh, '<:raw', $file or do {
            print $client "HTTP/1.1 500 Error\r\n\r\nCannot open file";
            close $client; next;
        };
        local $/;
        my $data = <$fh>;
        close $fh;

        my $type = $file =~ /\.html$/i ? 'text/html; charset=utf-8'
                 : $file =~ /\.css$/i  ? 'text/css'
                 : $file =~ /\.js$/i   ? 'text/javascript'
                 : $file =~ /\.png$/i  ? 'image/png'
                 : 'application/octet-stream';

        printf $client "HTTP/1.1 200 OK\r\nContent-Type: %s\r\nContent-Length: %d\r\nAccess-Control-Allow-Origin: *\r\n\r\n",
            $type, length($data);
        print $client $data;
    } else {
        print $client "HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\n\r\nFile not found: $path";
    }
    close $client;
}
