export default function Footer() {
  return (
    <footer className="bg-[#042648] text-white py-8 mt-auto">
      <div className="max-w-7xl mx-auto px-4 text-center">
        <p className="text-sm opacity-70">
          &copy; {new Date().getFullYear()} Aprende a Querer. Todos los derechos reservados.
        </p>
      </div>
    </footer>
  );
}
