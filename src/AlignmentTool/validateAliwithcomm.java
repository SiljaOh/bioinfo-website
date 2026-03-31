package AlignmentTool;
import java.io.*; // Ein-/Ausgabe
import java.util.*; // Listen, Sets, Locale

public class validateAliwithcomm {

    static class B { // Ein Block mit 1 Header + 4 Alignment-Zeilen
        String h,a,b,c,d; // h=Header, a/b=candidate, c/d=reference
    }

    static String seq(String s){return s.contains(":")?s.substring(s.indexOf(':')+1).trim():s.trim();} // Nur Sequenz nach ":" holen

    static Set<Long> pairs(String x,String y){ // Alle aligned residue-Paare als Set
        if(x.length()!=y.length())throw new IllegalArgumentException("Alignment lines must have same length"); // Gleiche Länge nötig
        Set<Long> r=new HashSet<>(); // Ergebnis-Set
        int i=0,j=0; // echte Positionen ohne Gaps
        for(int k=0;k<x.length();k++){ // Durch Alignment laufen
            char a=x.charAt(k),b=y.charAt(k); // Zeichen an Stelle k
            if(a!='-'&&b!='-'){r.add(((long)i<<32)|(j&0xffffffffL));i++;j++;} // echtes Paar speichern
            else if(a!='-')i++; // nur seq1 weiter
            else if(b!='-')j++; // nur seq2 weiter
        }
        return r; // Set zurück
    }

    static List<int[]> pairList(String x,String y){ // Alle aligned Paare als Liste [i,j]
        if(x.length()!=y.length())throw new IllegalArgumentException("Alignment lines must have same length"); // Gleiche Länge nötig
        List<int[]> r=new ArrayList<>(); // Ergebnisliste
        int i=0,j=0; // echte Positionen ohne Gaps
        for(int k=0;k<x.length();k++){ // Durch Alignment laufen
            char a=x.charAt(k),b=y.charAt(k); // Zeichen an Stelle k
            if(a!='-'&&b!='-'){r.add(new int[]{i,j});i++;j++;} // echtes Paar speichern
            else if(a!='-')i++; // nur seq1 weiter
            else if(b!='-')j++; // nur seq2 weiter
        }
        return r; // Liste zurück
    }

    static double sens(Set<Long> ref,Set<Long> cand){ // Sensitivity
        if(ref.isEmpty())return 0; // Sonderfall
        int tp=0; // true positives
        for(Long p:ref)if(cand.contains(p))tp++; // gemeinsame Paare zählen
        return (double)tp/ref.size(); // Anteil korrekter Referenzpaare
    }

    static double spec(Set<Long> ref,Set<Long> cand){ // Specificity
        if(cand.isEmpty())return 0; // Sonderfall
        int tp=0; // true positives
        for(Long p:cand)if(ref.contains(p))tp++; // gemeinsame Paare zählen
        return (double)tp/cand.size(); // Anteil korrekter Kandidatenpaare
    }

    static double cov(Set<Long> ref,Set<Long> cand){ // Coverage
        if(cand.isEmpty())return 1;
        Set<Integer> a=new HashSet<>(),b=new HashSet<>(); // Zielpositionen aus ref/cand
        for(Long p:ref)a.add((int)(p&0xffffffffL)); // j-Position aus Referenz
        for(Long p:cand)b.add((int)(p&0xffffffffL)); // j-Position aus Kandidat
        int n=0; // Schnittmenge
        for(Integer j:b)if(a.contains(j))n++; // gemeinsame Zielpositionen zählen
        return (double)n/b.size(); // Anteil
    }

    static double mse(List<int[]> ref,List<int[]> cand){ // Mean shift error
        if(ref.isEmpty())return 0; // Sonderfall
        int m=0; // größter i-Wert
        for(int[] p:ref)m=Math.max(m,p[0]); // max aus Referenz
        for(int[] p:cand)m=Math.max(m,p[0]); // max aus Kandidat
        int[] map=new int[m+1]; // map[i]=j im Kandidaten
        Arrays.fill(map,-1); // -1 = nicht vorhanden
        for(int[] p:cand)map[p[0]]=p[1]; // Kandidaten-Mapping bauen
        long sum=0; int n=0; // Summe und Anzahl
        for(int[] p:ref)if(map[p[0]]>=0){sum+=Math.abs(p[1]-map[p[0]]);n++;} // Shifts aufsummieren
        return n==0?0:(double)sum/n; // Mittelwert
    }

    static double imse(List<int[]> ref,List<int[]> cand){ // Inverse mean shift error
        if(ref.isEmpty())return 0; // Sonderfall
        int m=0; // größter j-Wert
        for(int[] p:ref)m=Math.max(m,p[1]); // max aus Referenz
        for(int[] p:cand)m=Math.max(m,p[1]); // max aus Kandidat
        int[] map=new int[m+1]; // map[j]=i im Kandidaten
        Arrays.fill(map,-1); // -1 = nicht vorhanden
        for(int[] p:cand)map[p[1]]=p[0]; // Kandidaten-Mapping bauen
        long sum=0; int n=0; // Summe und Anzahl
        for(int[] p:ref)if(map[p[1]]>=0){sum+=Math.abs(p[0]-map[p[1]]);n++;} // inverse Shifts aufsummieren
        return n==0?0:(double)sum/n; // Mittelwert
    }

    public static void main(String[] args) throws Exception { // Startpunkt
        String f=null; // Dateiname
        for(int i=0;i<args.length-1;i++)if(args[i].equals("-f"))f=args[i+1]; // -f suchen
        if(f==null){System.out.println("Usage: java -jar validateAli.jar -f <alignment-pairs>");return;} // Hilfe ausgeben

        List<B> bs=new ArrayList<>(); // Alle Blöcke
        try(BufferedReader br=new BufferedReader(new FileReader(f))){ // Datei öffnen
            String line,h=null,a=null,b=null; // temporäre Variablen
            while((line=br.readLine())!=null){ // Zeile lesen
                line=line.trim(); // trimmen
                if(line.isEmpty())continue; // Leerzeilen überspringen
                if(line.startsWith(">")){h=line;a=b=null;continue;} // neuer Block startet
                if(a==null){a=line;continue;} // erste Alignmentzeile
                if(b==null){b=line;continue;} // zweite Alignmentzeile
                String c=line; // dritte Alignmentzeile
                String d=br.readLine(); // vierte Alignmentzeile
                if(d==null)break; // unvollständiger Block
                d=d.trim(); // trimmen
                if(d.isEmpty()){h=a=b=null;continue;} // unvollständig -> überspringen
                B x=new B(); // neuen Block anlegen
                x.h=h.substring(1).trim();x.a=a;x.b=b;x.c=c;x.d=d; // Werte setzen
                bs.add(x); // Block speichern
                h=a=b=null; // zurücksetzen
            }
        }

        for(B x:bs){ // Jeden Block auswerten
            String a1=seq(x.a),a2=seq(x.b),r1=seq(x.c),r2=seq(x.d); // Sequenzen extrahieren
            Set<Long> rp=pairs(r1,r2),cp=pairs(a1,a2); // Referenz- und Kandidatenpaare
            List<int[]> rl=pairList(r1,r2),cl=pairList(a1,a2); // Referenz- und Kandidatenlisten
            double s=sens(rp,cp),p=spec(rp,cp),c=cov(rp,cp),m=mse(rl,cl),im=imse(rl,cl); // Metriken berechnen
            System.out.printf(Locale.US, ">%s %.4f %.4f %.4f %.4f %.4f%n",x.h,s,p,c,im,m); // Header mit Scores ausgeben
            System.out.println(x.a); // candidate seq1
            System.out.println(x.b); // candidate seq2
            System.out.println(x.c); // reference seq1
            System.out.println(x.d); // reference seq2
        }
    }
}
